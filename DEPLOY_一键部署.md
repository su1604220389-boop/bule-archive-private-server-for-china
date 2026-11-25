# 《一键部署文档》· BA 私服（20261120 补丁交付包配套）

- 适用对象：**有点 Linux 基础、但不是本项目作者**的人。照着从上往下敲，能把整套服搭起来。
- 文档口径：**只写部署**。本文不修改任何代码、不动交付包、不含任何真实口令/密钥/域名/IP；凡是需要你填的地方一律是 `<尖括号占位符>`（**替换时把尖括号一起换掉**）。
- 阅读顺序：「这个包是什么」→「5 分钟速览」→ §1 → §2 → §3（10 步）→ §6 验收 → 出问题查 §7。文中体积/条数都是**实测值**，数字对不上就是那步没成，别往下走。

---

> **0. 这个包是什么 / 不是什么（先说清）**
>
> **是**：一整套「在**上游开源服务端**基础上做的 **补丁 + 配置 + 管理面板 + 客户端补丁 + 文档**」。
> 具体包括：桥（`account_auth_probe.py`，线上真身）与 90004 补丁脚本、我们编译的 `Shittim-Server.dll`/`Schale.dll`、自有 `Data/*.json` 与 7 份客户端 id 白名单、`ClientItemFilter.cs` 源码单件、管理站（整站 + 5 个改动页）、nginx/systemd 线上配置参考、APK 补丁与 smali、以及 423 份文档。
>
> **不是**：**不含服务端完整源码**（只有上游的编译产物与我们自己的补丁源码单件）、**不含客户端 APK**（只有补丁脚本与签名材料）、**不含数据库**（服务端 SQLite、桥的 accounts.db、管理站 MySQL 全部要你在本机生成）、**不含证书私钥**（nginx 配置里只有路径字符串）。
>
> ⇨ **「不含」= 你要自己去拿**。清单在 §1，缺一样都起不来；最容易漏的三样是：**上游能编过 .NET 10 的源码**、**国服 3.0.2 原版 APK**、**真证书的域名**。
>
> 🔎 **脱敏提示**：本包**已脱敏**（真实口令 / 域名 / 公网 IP / 证书路径 / 设备指纹 / 令牌一律换成 `<REDACTED_*>` 一类占位符，逐条清单见 `REDACTION.md`）。**如发现任何 `<REDACTED_*>` 之外的可疑真实凭据，请立即反馈**（不要直接拿去部署）。

**5 分钟速览**（三条命令 + 一句话验收；下面全部展开在 §3）

```bash
# ① 装 .NET 10 并把上游编译到 /www/wwwroot/ba_srv（§3.1）
bash dotnet-install.sh --channel 10.0 --install-dir /root/dotnet10 && /root/dotnet10/dotnet publish Shittim-Server/Shittim-Server.csproj -c Release -o /www/wwwroot/ba_srv
# ② 应用服务端补丁（DLL + Data + Resources）并装三个 systemd 单元（§3.2 / §3.3）
systemctl daemon-reload && systemctl enable --now ba-shittim ba-sdk ba-bridge
# ③ 跑 90004 补丁校验（§3.5，这是全套里最重要的一个补丁）
cd /www/wwwroot/bapatch/tools && python3 verify_90004.py
```

**一句话验收**：`verify_90004.py` 最后一行打出 `RESULT: PASS`，且 `Data` 条数是 **Banners 7 / Notices 6 / Events 14 / GachaProbabilityDisplay 12** —— 打出这个，招募界面就不会是红字。

---

## 1. 前置准备清单

### 1.1 要什么 / 从哪来 / 大概多少 / 备注

| 要什么 | 从哪来 | 大概多少 | 备注 |
|---|---|---|---|
| **上游服务端 `Shittim-Server`**（.NET 10）+ 配套 DTO 库 `Schale` | 自行获取（上游开源仓库/发行版）。**必须是能编过 .NET 10 的版本** | 源码 ~2 MB；完整 publish 目录数十 MB（本包两个 DLL 合计 ~8 MB） | 本包的 `Shittim-Server.dll` 是**某一次构建产物**（`c013f442…` / 2,727,424 B）。若你的上游版本与它不同，**建议重新编译**（§3.1 的 A 路线），再按 §4 把补丁落回源码；B 路线（直接覆盖 DLL）只在「上游版本与包内一致」时可靠 |
| **.NET 10 SDK** | `dot.net/v1/dotnet-install.sh` 或发行版仓库 | ~300 MB | 版本要求：**10.0.100**（`global.json` 写 `"version": "10.0.100"`、`rollForward: latestFeature`）。TFM 是 `net10.0`，EF Core / Sqlite 是 10.0.10。**.NET 8/9 编不过** |
| **客户端：国服《蔚蓝档案》3.0.2 APK** | 自行获取原版安装包 | **~2.13 GB**（41,312 条目） | 包名 `com.RoamingStar.BlueArchive`，versionCode 73。必须是**国服原版**（不要日服/国际服），且没被别的补丁改过 |
| **服务器** | 云主机/独服，Linux x86_64 | 磁盘 ≥ 40 GB 可用；**内存 ≥ 2 GB 更稳** | 本项目实测在 **1.6 GB 内存**上能跑（见 §7 第 10 条），但 `dotnet` 峰值 ~200 MB、MySQL ~190 MB，1.6 GB 会紧到随时 OOM。系统：Alibaba Cloud Linux / Ubuntu 22.04 均可 |
| **域名 + TLS 证书** | 域名注册商 + Let's Encrypt 或商业 CA | 域名 ~¥30/年 | **客户端直连需要真证书，自签不行**。建议一张**泛域名证书** `*.<SERVER_DOMAIN>`，或把 `state-api` / `stateqc-api` / `gs-api` / `sdk` 四个名字都写进 SAN（§3.6） |
| **数据库** | 本机安装 | SQLite 0（服务端自建）/ MySQL ~200 MB | **服务端 SQLite**：上游自建（`BlueArchive.db` / `shittim.sqlite3`），**不需要你导入任何 SQL**。**MySQL**：只给管理站用（5.7 / 8.0 / MariaDB 10.2+） |
| **PHP** | 本机安装 | ~50 MB | **8.2**（管理站 `installed.lock` 记录为 8.2.31），需 `pdo_mysql`、`mbstring`、`json`。7.4 未测 |
| **Python** | 系统自带 | — | 服务器侧 **3.10+**（实测 3.10.12）；客户端打包脚本要求 **3.12** + `openssl` |
| **nginx** | 本机安装 | — | 需要 `ssl`、`stream`（仅当你要做 SNI 分流；本方案不需要）、`http2` 可选 |
| **apktool / jadx** | **不需要** | — | 客户端补丁用的是自研纯 Python 构建器（单文件、零依赖），不依赖 apktool 回编 |

### 1.2 端口规划表

| 端口 | 进程 | 监听地址 | 对外？ | 说明 |
|---|---|---|---|---|
| **5000** | `Shittim-Server.dll` | `0.0.0.0`（建议改成 `127.0.0.1`） | **否** | 游戏 API（`/api/*` 最终落这里，但只该由桥访问） |
| **5100** | 同上 | 同上 | **否** | Gateway（`/api/gateway`，multipart 的 `mx` 字段） |
| **9097** | `account_auth_probe.py`（桥） | `127.0.0.1`（代码写死） | **否** | 所有 `/api/*` 的入口；负责吸收/转发/套信封 |
| **8080** | `sdkcard.py` | `127.0.0.1`（建议） | **否** | 卡密 SDK：`/common/config`、`/user/login`、`/user/quick-login` |
| **8081** | nginx（管理站 vhost） | 按需 | 建议仅内网/办公 IP | 管理站 `ba_cardadmin`（PHP + MySQL） |
| **80** | nginx | `0.0.0.0` | **是** | 证书签发 + `state-api` 明文入口（`--gmconfig-url` 默认 `http`） |
| **443** | nginx | `0.0.0.0` | **是** | 同一套 vhost 的 TLS 版本（`gs-api` / `sdk` 走这里） |

> **443 冲突警告**：上游服务端在「发现证书」时会自己去 `Listen(443, UseHttps)`（`CLI/GameServer.cs`）。**`ba_srv/Config/` 下不要放证书**，443 留给 nginx。另：线上还有个 9098 的 state 生成器，**本包不含**，用 §3.6 的静态 `api-state.json` 替代即可。

### 1.3 磁盘 / 内存预算

| 项 | 占用 | 备注 |
|---|---|---|
| 上游编译产物 + 服务端 SQLite | ~10 MB + 数十 MB 起 | `/www/wwwroot/ba_srv`；SQLite 随玩家增多而涨 |
| **Excel 表（首次启动自动下载）** | **1–2 GB**（`Resources/Downloaded` + `Resources/Dumped`） | 首次启动必须能**出网**；也可自备 `Resources/Dumped/ExcelDB.db` 后设 `UseCustomExcel=true` |
| 桥 tools + 90004 数据 | ~40 MB（182 个文件 + `account_auth_probe.py.*` 历史备份）+ 10,883 B | 历史备份可清 |
| 客户端构建工作区 | **≥ 8 GB 空闲** | 2.13 GB 输入 + 2.13 GB 输出 + 临时文件 |
| 管理站 + MySQL | ~250 MB | |

### 1.4 交付包里到底有什么（与本文的对应关系）

| 包内目录 | 是什么 | 本轮部署是否需要 |
|---|---|---|
| `server/` | 线上同款 `Shittim-Server.dll`、`Schale.dll`、`Data/*.json`、`Resources/Client*.txt`、`ClientItemFilter.cs` | **要**（§3.2） |
| `bridge/` | 线上真身桥脚本 + 90004 补丁/校验脚本 + `expected_90004.json` + `_history/` 旧版 + systemd 说明 | **要**（§3.4 / §3.5） |
| `bridge_tools/` | `tools/` 整目录（182 个）、`_ba_state/`、`cn_*.txt` 开关、补丁脚本 | **要**（§3.4） |
| `server_config/` | 线上 nginx（98 个配置）+ 3 个 systemd 单元 | systemd **要**（§3.3）；nginx **只作参考**（§3.6） |
| `panel_full/ba_cardadmin/` | 管理站整站快照（53 个站点文件 + 清单） | **要**（§3.8） |
| `panel/` | 6 个精选改动页（与整站里同名文件一致） | 不需要（对照用） |
| `client/` | APK 构建器 `build_noroot_apk.py`、签名材料、smali、实验脚本 | **要**（§3.9） |
| `docs/` + `docs_all/` | 18 份精选 + 423 份全集 | 排障时查（§7 会指名看哪份） |

> `server_config/nginx/` 是**出包环境的原样配置**（含域名、证书路径、私有 CA 路径），**不要整目录覆盖**：按 §3.6 写自己的最小 vhost。里面 `ba_mitm.conf` / `tcp/ba_sni.conf` 是 MITM 试验，新部署**用不到**。

---

## 2. 目录与端口规划

### 2.1 线上目录树（照这个建，后面命令都按它写）

```text
/www/wwwroot/
├─ ba_srv/                      # 上游服务端发布目录（§3.1）
│  ├─ Shittim-Server.dll  Schale.dll  ...（依赖 DLL 一堆）
│  ├─ appsettings.json
│  ├─ Config/                   # 首启生成 Config.json；Gateway*.pem 放这里
│  ├─ Data/                     # GachaRecruitBanners.cn.json(529) + gacha_rates.defaults.json(4 组)
│  ├─ Resources/                # Client*.txt 7 份白名单 + Downloaded/(下载) + Dumped/(解表)
│  └─ logs/
├─ bapatch/                     # 桥（§3.4）
│  ├─ tools/                    # 182 个文件：account_auth_probe.py / cn_*.py / gen*.py / schema_sqlite.sql
│  ├─ logs/                     # api_all_requests.log / bridge_stdout.log / acct_svc.log
│  ├─ data/accounts.db          # 桥的账号库（§3.4 自己 init）
│  ├─ _ba_state/90004_ops.json  # 90004 运营数据（§3.5）
│  └─ cn_*.txt                  # 27 个根级开关（桥按「脚本目录 → bapatch 根」顺序找）
├─ _ba_state/state-api/api-state.json   # 你自己写的 /api/state 静态应答（§3.6）
├─ ba_sdk/                      # 卡密 SDK（§3.7）
│  ├─ sdkcard.py   cards.json   pay.json   ban_message.py
│  └─ resp/                     # common_config.json 等 10 份应答模板
├─ ba_cardadmin/                # 管理站（§3.8）
└─ ba_pkg/                      # 解压出来的交付包（只读，部署完可删）

/etc/systemd/system/ba-shittim.service  ba-sdk.service  ba-bridge.service
/www/wwwlogs/                             # nginx 日志
```

### 2.2 包内 → 线上 映射表

| 包内（解压后） | 线上目标 | 动作 |
|---|---|---|
| `server/Shittim-Server.dll`、`server/Schale.dll` | `/www/wwwroot/ba_srv/` | 覆盖（先备份） |
| `server/Data/GachaRecruitBanners.cn.json` | `/www/wwwroot/ba_srv/Data/` | 覆盖 |
| `server/Data/gacha_rates.defaults.json` | `/www/wwwroot/ba_srv/Data/` | **新增** |
| `server/Resources/Client*.txt`（7 份） | `/www/wwwroot/ba_srv/Resources/` | 覆盖/新增 |
| `server/Services/ClientItemFilter.cs` | **不上线** | 只在 §3.1-A 重编译时拷进源码 `Services/` |
| `bridge/account_auth_probe.py` | `/www/wwwroot/bapatch/tools/` | 覆盖 |
| `bridge/patch_90004.py`、`dto90004.py`、`expected_90004.json`、`verify_90004.py`、`check_patch_90004.py` | `/www/wwwroot/bapatch/tools/` | 新增 |
| `bridge_tools/tools/*` | `/www/wwwroot/bapatch/tools/` | 整目录复制 |
| `bridge_tools/_ba_state/90004_ops.json` | `/www/wwwroot/bapatch/_ba_state/` | 新增 |
| `bridge_tools/cn_*.txt`（根级 27 个） | `/www/wwwroot/bapatch/` | 新增 |
| `server_config/systemd/ba-*.service`（3 个） | `/etc/systemd/system/` | 新增 |
| `panel_full/ba_cardadmin/*` | `/www/wwwroot/ba_cardadmin/` | 整站复制 |
| `client/*`、`docs/`、`docs_all/` | 本地（构建机/文档机） | 不上服务器 |

> 目录名不是 100% 硬约束：**以 zip 内 `MANIFEST.txt` 为准**。§2.3 给了 `find` 命令，按文件名找，别死记路径。

### 2.3 先把包摊开，按名字找文件（**第一步就做这个**）

```bash
mkdir -p /root/ba_pkg
unzip -q /root/BA_自研补丁_20261120.zip -d /root/ba_pkg
cd /root/ba_pkg && find . -maxdepth 2 -type d | sort

# 逐个确认关键文件在哪（输出为空 = 包里没有，去 §1 自己补）
find /root/ba_pkg -name 'Shittim-Server.dll' -size +2M
find /root/ba_pkg -name 'account_auth_probe.py' -size +200k
find /root/ba_pkg -name 'ba-bridge.service' -o -name 'ba-shittim.service'
find /root/ba_pkg -name 'account_service.py' -o -name 'schema_sqlite.sql'
find /root/ba_pkg -path '*ba_cardadmin/index.php'
find /root/ba_pkg -name 'build_noroot_apk.py'
```

下面所有命令里的 `/root/ba_pkg/<子目录>` 如果与你 `find` 出来的不一致，**以 find 结果为准**替换即可。

---

## 3. 部署步骤（每一步都可复制粘贴，带验收）

### 3.1 第 1 步：装 .NET 10 → 编译上游 → 放到 `/www/wwwroot/ba_srv`

**A 路线（推荐）：自己编译**

```bash
# 1) 装 .NET 10 SDK 到 /root/dotnet10
cd /root
curl -fsSL https://dot.net/v1/dotnet-install.sh -o dotnet-install.sh
bash dotnet-install.sh --channel 10.0 --install-dir /root/dotnet10
export DOTNET_ROOT=/root/dotnet10
export PATH=$DOTNET_ROOT:$PATH

# 验收：必须能看到 10.0.1xx
dotnet --list-sdks
```

```bash
# 2) 拿上游源码（换成你手上的上游地址/发行包）
cd /root
git clone <上游仓库地址> shittim-src && cd shittim-src

# 3) 发布到 /www/wwwroot/ba_srv
mkdir -p /www/wwwroot/ba_srv
/root/dotnet10/dotnet publish Shittim-Server/Shittim-Server.csproj \
  -c Release -o /www/wwwroot/ba_srv --nologo
```

**验收 1**：`test -f /www/wwwroot/ba_srv/Shittim-Server.dll && echo OK` → `OK`
**验收 2**：网关密钥对必须在（丢了客户端会卡在「Unpacking game resources」，§7 第 14 条）：

```bash
ls -l /www/wwwroot/ba_srv/Config/GatewayPrivateKey.pem /www/wwwroot/ba_srv/Config/GatewayPublicKey.pem
# 没有就补（源码里带）
cp -n /root/shittim-src/Shittim-Server/config/GatewayPrivateKey.pem /www/wwwroot/ba_srv/Config/
cp -n /root/shittim-src/Shittim-Server/config/GatewayPublicKey.pem  /www/wwwroot/ba_srv/Config/
```

**验收 3（首次启动冒烟）**：会下载 Excel 表，给足时间；看到端口监听即算过。

```bash
cd /www/wwwroot/ba_srv
DOTNET_ROOT=/root/dotnet10 DOTNET_gcServer=0 DOTNET_GCHeapHardLimit=0x40000000 \
  timeout 180 /root/dotnet10/dotnet Shittim-Server.dll --console --id 2
# 期望日志：[Version Resolver] Initialized … / [Resource Manager] Checking Excel tables… / HTTP on ports 5000 (API) & 5100 (Gateway)
```

```bash
# 另开一个终端验收
ls -l /www/wwwroot/ba_srv/Config/Config.json          # 首启生成
du -sh /www/wwwroot/ba_srv/Resources/Dumped           # 非空
ss -lntp | grep -E ':(5000|5100)\b'
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5000/health   # 期望 200
```

> 首次冒烟用 `timeout` 跑前台即可（跑完自动结束），常驻交给 §3.3 的 systemd。
>
> **重编译时把 §4 的 C# 补丁落回源码**：`ClientItemFilter.cs` 直接拷进 `Shittim-Server/Services/`，`Core/HandlerManager.cs` 的出口钩子、`Services/ShopManager.cs` 的空引用早退、响应壳对齐，按 `docs_all/.../EXPORT_FILTER.md`、`SHOPLIST_NRE_FIX.md`、`ENVELOPE_ALIGN.md` 三份文档里的 diff 改。

**B 路线（用包里的 DLL 覆盖）**：只在「你的上游版本与包内一致」时可靠——前提是 `/www/wwwroot/ba_srv` 已经是同一版本上游的 publish 结果。

```bash
install -m 0644 /root/ba_pkg/server/Shittim-Server.dll /www/wwwroot/ba_srv/Shittim-Server.dll
install -m 0644 /root/ba_pkg/server/Schale.dll         /www/wwwroot/ba_srv/Schale.dll
```
验收同 A 路线；**启动日志里必须出现 `loaded 1803 client item id(s)` 与 `item export filter is ON`**，没有就说明 B 路线版本不匹配，回 A 路线。

### 3.2 第 2 步：应用服务端补丁（每份文件去哪，逐个说清）

| 包内文件 | 线上去向 | 作用 | 覆盖后必须看到的证据 |
|---|---|---|---|
| `server/Shittim-Server.dll` | `/www/wwwroot/ba_srv/Shittim-Server.dll` | 出口过滤 + 响应壳 + Shop_List 空引用 + 抽卡概率可配（全部编在这一个 DLL 里） | 启动日志 `loaded 1803 client item id(s)`、`[GachaRates] boot` 4 行 |
| `server/Schale.dll` | `/www/wwwroot/ba_srv/Schale.dll` | 配套 DTO 库（与 DLL 同一次构建） | 启动无 `FileLoadException` |
| `server/Data/GachaRecruitBanners.cn.json` | `/www/wwwroot/ba_srv/Data/` | 卡池清单 **529 条** | `ShopRecruits = 529` |
| `server/Data/gacha_rates.defaults.json` | `/www/wwwroot/ba_srv/Data/` | 4 组默认出货阈值（312 B） | `[GachaRates] boot Normal: ... ssrThreshold=30` |
| `server/Resources/Client*.txt`（7 份） | `/www/wwwroot/ba_srv/Resources/` | 客户端 id 白名单（道具 1803 / 角色 7223 / 徽章 1065 / 装备 191 / 家具 876 / 记忆大厅 258 / 武器 254） | 启动日志 `1803`；`/api/item/list` 不再让客户端解析失败 |
| `server/Services/ClientItemFilter.cs` | **不上线** | 过滤逻辑源码单件 | 仅在 A 路线重编译时使用 |

```bash
BK=/root/ba_srv_before_patch_$(date +%Y%m%d_%H%M%S); mkdir -p "$BK"
cp -a /www/wwwroot/ba_srv/Shittim-Server.dll /www/wwwroot/ba_srv/Schale.dll "$BK"/
cp -a /www/wwwroot/ba_srv/Data "$BK"/Data 2>/dev/null
sha256sum "$BK"/Shittim-Server.dll

install -m 0644 /root/ba_pkg/server/Shittim-Server.dll /www/wwwroot/ba_srv/Shittim-Server.dll
install -m 0644 /root/ba_pkg/server/Schale.dll         /www/wwwroot/ba_srv/Schale.dll
mkdir -p /www/wwwroot/ba_srv/Data /www/wwwroot/ba_srv/Resources
install -m 0644 /root/ba_pkg/server/Data/GachaRecruitBanners.cn.json /www/wwwroot/ba_srv/Data/
install -m 0644 /root/ba_pkg/server/Data/gacha_rates.defaults.json   /www/wwwroot/ba_srv/Data/
install -m 0644 /root/ba_pkg/server/Resources/Client*.txt             /www/wwwroot/ba_srv/Resources/

# 验收：三个指纹必须对上
sha256sum /www/wwwroot/ba_srv/Shittim-Server.dll
# c013f4427ad01d44c00cc63af3de817b800638fcd8ec0ee55de41126aed106aa  (2,727,424 B)
sha256sum /www/wwwroot/ba_srv/Data/GachaRecruitBanners.cn.json
# 3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77
grep -c '"Id"' /www/wwwroot/ba_srv/Data/GachaRecruitBanners.cn.json   # 529
```

重启（此时 §3.3 若还没装，就用 §3.1 的前台方式起一次看日志）：

```bash
systemctl restart ba-shittim
for i in $(seq 1 30); do ss -lnt | grep -q ':5000' && ss -lnt | grep -q ':5100' && { echo "5000/5100_UP ${i}s"; break; }; sleep 1; done
tail -n 40 /var/log/ba-shittim.log | grep -E 'ClientItemFilter|GachaRates|Now listening|HTTP on ports'
```

**回滚**：`install -m 0644 "$BK"/Shittim-Server.dll /www/wwwroot/ba_srv/ && rm -f /www/wwwroot/ba_srv/Data/gacha_rates.defaults.json && systemctl restart ba-shittim`。

### 3.3 第 3 步：装 systemd 三个单元

三个单元在 `server_config/systemd/`。**它们带着出包环境的路径**，装之前必须改下面 6 处：

| 单元 | 要改的地方 | 出包环境的值（示例形态） | 改成 |
|---|---|---|---|
| `ba-shittim.service` | `WorkingDirectory`、`ExecStart` 里的 DLL 路径 | `/www/wwwroot/ba_srv` | `<SRV_ROOT>`（本文按 `/www/wwwroot/ba_srv`） |
| `ba-shittim.service` | `DOTNET_ROOT`、`ExecStart` 的 dotnet 路径 | `/root/dotnet10` | `<DOTNET_ROOT>` |
| `ba-shittim.service` | `User` | `root` | `<RUN_USER>`（简单起见留 root，但**生产建议专用用户**） |
| `ba-bridge.service` | `WorkingDirectory`、`ExecStart` | `/www/wwwroot/bapatch/tools` | `<BAPATCH_ROOT>/tools` |
| `ba-bridge.service` | 两行 `StandardOutput/StandardError=append:` | `/www/wwwroot/bapatch/logs/bridge_stdout.log` | 自己路径（**目录必须先存在**，否则服务起不来） |
| `ba-sdk.service` | `WorkingDirectory`、`ExecStart`、IP | `/www/wwwroot/ba_sdk`、`/var/log/ba-sdk.log` | `<SDK_ROOT>` |

```bash
install -m 0644 /root/ba_pkg/server_config/systemd/ba-shittim.service /etc/systemd/system/
install -m 0644 /root/ba_pkg/server_config/systemd/ba-sdk.service      /etc/systemd/system/
install -m 0644 /root/ba_pkg/server_config/systemd/ba-bridge.service   /etc/systemd/system/

# 按上表逐份改（vi 最稳）。若你的路径与本文不同，可参照下面两行（先去注释、把 <> 换成实际路径再跑）
# sed -i 's#/www/wwwroot/ba_srv#<SRV_ROOT>#g; s#/root/dotnet10#<DOTNET_ROOT>#g' /etc/systemd/system/ba-shittim.service
# sed -i 's#/www/wwwroot/bapatch#<BAPATCH_ROOT>#g' /etc/systemd/system/ba-bridge.service
mkdir -p /www/wwwroot/bapatch/logs /var/log
grep -nE 'User=|WorkingDirectory=|ExecStart=|StandardOutput=|StandardError=' /etc/systemd/system/ba-*.service
```

```bash
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/ba-shittim.service /etc/systemd/system/ba-sdk.service /etc/systemd/system/ba-bridge.service
systemctl enable --now ba-shittim ba-sdk ba-bridge

# 验收
systemctl is-active ba-shittim ba-sdk ba-bridge     # active active active
systemctl is-enabled ba-shittim ba-sdk ba-bridge    # enabled ...
ss -lntp | grep -E ':(5000|5100|9097|8080)\b'
```

> `ba-shittim` 是 `Type=forking` + `tmux`（为了保留控制台命令）：**不要改成 `Type=simple`**，否则 `ExecStop=tmux kill-session` 失效、重启出双实例。

### 3.4 第 4 步：部署桥（最容易踩坑的一步）

```bash
mkdir -p /www/wwwroot/bapatch/{tools,logs,data,_ba_state}

# 1) tools 整目录（182 个文件）
cp -a /root/ba_pkg/bridge_tools/tools/. /www/wwwroot/bapatch/tools/

# 2) 根级 cn_*.txt 开关（27 个；少了它们桥会走默认分支，行为静默变化）
find /root/ba_pkg/bridge_tools -name 'cn_*.txt' -not -path '*/tools/*' -print0 | xargs -0 -r cp -a -t /www/wwwroot/bapatch/
ls /www/wwwroot/bapatch/cn_*.txt | wc -l          # 期望 27（若带 .bak 变体会多 1–2 个，正常）
ls /www/wwwroot/bapatch/tools/cn_*.txt            # 期望 3 个：1005 / 26000 / 4000

# 3) 90004 运营数据
cp -a /root/ba_pkg/bridge_tools/_ba_state/90004_ops.json /www/wwwroot/bapatch/_ba_state/
sha256sum /www/wwwroot/bapatch/_ba_state/90004_ops.json
# 938ae90855b5fa5fa11342854f2e0f28e7130b466c303621151685efc06107fb  (10,883 B)

# 4) 桥的账号库（包里不含 DB，必须自己建表）
cd /www/wwwroot/bapatch/tools
python3 account_service.py --init-db --db /www/wwwroot/bapatch/data/accounts.db
python3 account_service.py --stats --db /www/wwwroot/bapatch/data/accounts.db | head

# 5) 开关形态：cn_bridge_mode.txt 期望 bridge（forward = 原样透传）；tools/cn_4000.txt 期望 0（0 = 转发，1 = 回桩）
cat /www/wwwroot/bapatch/cn_bridge_mode.txt /www/wwwroot/bapatch/tools/cn_4000.txt
```

起服务并**验证 cwd**（这是本步的核心验收，理由见 §7 第 1 条）：

```bash
systemctl enable --now ba-bridge
sleep 2
systemctl is-active ba-bridge
PID=$(systemctl show -p MainPID --value ba-bridge); echo "pid=$PID"
readlink /proc/$PID/cwd        # 必须 = /www/wwwroot/bapatch/tools
pgrep -fc account_auth_probe.py   # 必须 = 1
ss -lntp | grep ':9097'
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9097/    # 期望 200
```

**常见的起不来原因**：`logs/` 目录不存在（systemd `append:` 打不开文件）、`tools/` 少文件（`cn_cipher.py`/`cn_wire.py`/`cn_inner.py`/`cn_inner27.py`/`cn_nick.py` 必须都在）、`python3` 路径不是 `/usr/bin/python3`（改 `ExecStart`）。

### 3.5 第 5 步：跑 90004 补丁（**全套里最重要的一个**）

**先搞清楚一件事**：`bridge/account_auth_probe.py` 是**线上真身，`90004-PATCH v1` 已经打在里面**（文件开头有 `# ==== BEGIN 90004-PATCH v1`）。所以正常情况**不用再打一遍**，只要：① 确认补丁在（`--verify` PASS）② 确认 `_ba_state/90004_ops.json` 在 ③ 跑验证脚本把结构与条数钉死。

```bash
cd /www/wwwroot/bapatch/tools
ls -l account_auth_probe.py       # 228,775 B 为线上真身
sha256sum account_auth_probe.py   # 15758f0ea007dcfba4e46fc4620dd183329381c194f00878abd6acc21cd2ee01
grep -c 'BEGIN 90004-PATCH v1' account_auth_probe.py    # 期望 1

# 只校验，不写
python3 patch_90004.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --verify
# 期望：inline_data_keys=9 / inline_dirty_input=PASS / outer_requestid: synced / 结果: PASS
```

如果 `--verify` 报 FAIL（说明你把桥换成了没打补丁的版本），再执行：

```bash
# 备份由脚本自己生成（同目录 *.bak.90004.*），幂等：已经打过就什么都不改
python3 patch_90004.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --apply
python3 patch_90004.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --verify
# 可选：不联网跑一遍 90004 分支（把加密层 stub 掉）
python3 patch_90004.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --e2e
systemctl restart ba-bridge
```

**装验证脚本并喂一次 90004**（`verify_90004.py` 自己造请求、自己解信封，不依赖客户端）：

```bash
cp -f /root/ba_pkg/bridge/verify_90004.py /root/ba_pkg/bridge/expected_90004.json /www/wwwroot/bapatch/tools/
cd /www/wwwroot/bapatch/tools
python3 verify_90004.py --host 127.0.0.1 --port 9097 --dump /tmp/90004.inner.json
```

**期望输出（关键行）**：

```text
[PASS] HTTP 200                                   14016 bytes
[PASS] 顶层键集合（6 键）     Protocol SessionKey ServerTimeTicks ServerNotification RequestId Data
[PASS] Data 是 dict（不是 null/缺省）  9 键：Notices Events Issues Banners GachaProbabilityDisplay GuidePopup GachaPeriodDisplay RaidPeriodDisplay Survey
[PASS] Data 条数   Notices 6 / Events 14 / Issues 0 / Banners 7 / GachaProbabilityDisplay 12 / GuidePopup 0
[PASS] GachaPeriodDisplay / RaidPeriodDisplay / Survey 均为 null
31 checks / FAIL=0 / WARN=1
RESULT: PASS —— 90004 已是官方 6 层 + Data 9 键结构，与 expected_90004.json 一致
```

> 唯一允许的 `WARN` 是「`SessionKey` 为空」——桥重启后还没人登录过，正常。体积 **~14 KB（13–15 KB 区间）**；若只有 **~2 KB**，说明补丁没生效或 ops 文件没读到，回 §7 第 2 条。
>
> **换期**：`90004_ops.json` 里公告/活动/概率公示都带 `EndDate`（本包这批数据到 **2026-11-26 13:59:59**）。换期只做一件事：**替换这个 json + 重启桥**，不重打补丁、不动卡池、不动客户端。做法与数据来源见 `docs_all/work/ba/plan/20261119/GACHA_ROOTCAUSE_90004_FINAL.md` §4–§5。

### 3.6 第 6 步：配 nginx

**先写 `/api/state` 的静态应答**（客户端第一跳就是它；`State:0` 开服、`1` 维护）：

```bash
mkdir -p /www/wwwroot/_ba_state/state-api
cat > /www/wwwroot/_ba_state/state-api/api-state.json <<'JSON'
{"Servers":["http://gs-api.<SERVER_DOMAIN>/api/"],"State":0,"Msg":""}
JSON
chmod 644 /www/wwwroot/_ba_state/state-api/api-state.json
```

> 用 https 就把 `http://` 换成 `https://`，并保证证书覆盖该名字。`Servers` 里的数组就是客户端后续所有 `/api/*` 的根地址。

**公共 location 片段**（80/443 两个 server 都 include 它，避免抄两遍）：

```bash
mkdir -p /etc/nginx/snippets
cat > /etc/nginx/snippets/ba_api.conf <<'NGINX'
# 精确匹配优先于前缀匹配：/api/state 走静态文件，不进桥
location = /api/state {
    alias /www/wwwroot/_ba_state/state-api/api-state.json;
    default_type "application/json; charset=utf-8";
    add_header Cache-Control "no-store" always;
}
# 客户端健康探测：必须是 2 字节 "ok" + text/plain
location = /api/health { default_type text/plain; return 200 "ok"; }
# 管理 API 绝不对外（管理站走 127.0.0.1:5000 直连，见 §3.8）
location ^~ /api/admin/ { return 404; }
# 其余 /api/* 全部进桥
location ^~ /api/ {
    proxy_pass http://127.0.0.1:9097;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Connection "";
    client_max_body_size 32m;
    proxy_read_timeout 120s;
}
location / { return 404; }
NGINX
nginx -t
```

**游戏 API vhost**（`/etc/nginx/conf.d/ba-api.conf`；宝塔用户放 `/www/server/panel/vhost/nginx/`）：

```nginx
server {
    listen 80;
    listen 443 ssl;
    http2 on;                    # nginx < 1.25.1 请改成 listen 443 ssl http2;
    server_name state-api.<SERVER_DOMAIN> stateqc-api.<SERVER_DOMAIN> gs-api.<SERVER_DOMAIN>;

    ssl_certificate     /etc/nginx/cert/<SERVER_DOMAIN>.fullchain.pem;   # ← 你的真证书
    ssl_certificate_key /etc/nginx/cert/<SERVER_DOMAIN>.key;             # ← 你的私钥
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_timeout 10m;

    access_log /www/wwwlogs/ba_api.log;
    error_log  /www/wwwlogs/ba_api.error.log;

    include /etc/nginx/snippets/ba_api.conf;
}
```

**SDK 站点 vhost**（`sdk.<SERVER_DOMAIN>` → 8080，同样一份 server 兼顾 80/443）：

```nginx
server {
    listen 80;
    listen 443 ssl;
    http2 on;
    server_name sdk.<SERVER_DOMAIN>;
    ssl_certificate     /etc/nginx/cert/<SERVER_DOMAIN>.fullchain.pem;
    ssl_certificate_key /etc/nginx/cert/<SERVER_DOMAIN>.key;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 8m;
    }
}
```

```bash
nginx -t && systemctl reload nginx

curl -s http://127.0.0.1/api/state                       # {"Servers":["http://gs-api.<...>/api/"],"State":0,"Msg":""}
curl -s -H 'Host: gs-api.<SERVER_DOMAIN>' http://127.0.0.1/api/health   # ok（2 字节）
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: gs-api.<SERVER_DOMAIN>' http://127.0.0.1/api/admin/status   # 404（必须）
```

> 线上原来还有一层「SNI 分流 + 私有 CA + MITM」，那是**没改 GameMainConfig 时代的方案**；本包客户端补丁会把 state 地址直接改到你的域名（§3.9），所以**不需要 SNI/私有 CA**。

### 3.7 第 7 步：部署卡密 SDK 站点（`/www/wwwroot/ba_sdk`）

```bash
mkdir -p /www/wwwroot/ba_sdk
SDK=$(dirname "$(find /root/ba_pkg -name sdkcard.py -print -quit)")   # 通常随 server_config/ 或 bridge_tools/ 给出
cp -a "$SDK"/. /www/wwwroot/ba_sdk/
ls /www/wwwroot/ba_sdk
# 期望：sdkcard.py  cards.json  pay.json  ban_message.py  resp/（10 份 json）
```

**`resp/common_config.json` 必须自己填**（这是客户端启动时拉的 SDK 配置）：

```bash
python3 - <<'PY'
import json
p='/www/wwwroot/ba_sdk/resp/common_config.json'
d=json.load(open(p,encoding='utf-8'))
c=d['Data']['AppConfig']
# 1) 检测地址改成你自己的（客户端拿这个判断“能不能连上服务器”）
c['DetectionAddress']['HTTP']=['https://gs-api.<SERVER_DOMAIN>/api/health']
c['DetectionAddress']['MTR'] =['https://gs-api.<SERVER_DOMAIN>/api/health']
c['DetectionAddress']['Internet']='https://www.baidu.com'
# 2) 第三方上报/一键登录：没有对应账号就关掉，别把出包环境的 key 带出去
c['SLS']['ENABLE']=False
c['Captcha']['Enable']=False
c['Udata']['Enable']=False
json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,separators=(',',':'))
print('patched:', c['DetectionAddress']['HTTP'])
PY
chmod 644 /www/wwwroot/ba_sdk/resp/common_config.json
```

**卡密库 `cards.json`**（`sdkcard.py` 与后端都读它；自己造，别用包里示例）：

```bash
cat > /www/wwwroot/ba_sdk/cards.json <<'JSON'
{
 "cards": {
  "<第一张卡密>": {"devices": [], "expire": 0, "bind_one": true},
  "<第二张卡密>": {"devices": [], "expire": 0, "bind_one": true}
 }
}
JSON
touch /www/wwwroot/ba_sdk/sdk.log
chmod 644 /www/wwwroot/ba_sdk/cards.json /www/wwwroot/ba_sdk/sdk.log
```

> 字段含义：`devices` 已绑定设备列表（空=未绑定）、`expire` unix 秒（0=永不过期）、`bind_one` 一卡一机。**正式运营请用管理站生成**（§3.8），别手写。

**付费开关**：`pay.json` 里 `{"PayState":2,"DeliveryState":2,"Amount":3000}` 是「充值关闭」的安全默认，不想做支付就**保持原样**。

```bash
systemctl enable --now ba-sdk
for i in $(seq 1 15); do ss -lnt | grep -q ':8080' && { echo "8080_UP ${i}s"; break; }; sleep 1; done
ss -lntp | grep ':8080'
curl -s http://127.0.0.1:8080/common/config | head -c 120; echo
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: sdk.<SERVER_DOMAIN>' http://127.0.0.1/common/config   # 200
```

### 3.8 第 8 步：部署管理站（`/www/wwwroot/ba_cardadmin`）

**注意：包里没有 `install.php`**（线上装完按安全要求删掉了）。所以不能跑向导，要手工建库建表建管理员——下面 6 小步照着做。

```bash
# 1) 整站复制
mkdir -p /www/wwwroot/ba_cardadmin
cp -a /root/ba_pkg/panel_full/ba_cardadmin/. /www/wwwroot/ba_cardadmin/
ls /www/wwwroot/ba_cardadmin     # index.php login.php config.php config.php.example inc pages sql state

# 2) 建库（MySQL）
mysql -uroot -p <<'SQL'
CREATE DATABASE IF NOT EXISTS ba_cardadmin DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'ba_cardadmin'@'127.0.0.1' IDENTIFIED BY '<DB_PASSWORD>';
GRANT ALL PRIVILEGES ON ba_cardadmin.* TO 'ba_cardadmin'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL

# 3) 导入表结构（可重复执行）
mysql -uroot -p ba_cardadmin < /www/wwwroot/ba_cardadmin/sql/schema.sql
mysql -uroot -p -e 'use ba_cardadmin; show tables;'   # admins cards card_devices ... settings audit_log

# 4) 写 config.php（从模板复制，四要素 + 两个 key 全靠自己填）
cp /www/wwwroot/ba_cardadmin/config.php.example /www/wwwroot/ba_cardadmin/config.php
# 编辑它，改这 6 项：DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASS / APP_SECRET
# （APP_SECRET：php -r "echo bin2hex(random_bytes(32));"）
# 再补 4 行（模板里没有，但面板要用它连服务端 admin API 与卡密库）：
#   define('BA_ADMIN_BASE','http://127.0.0.1:5000');
#   define('BA_ADMIN_KEY','<AdminApiKey>');  # 必须与 ba_srv/Config/Config.json 的 AdminApiKey 一致
#   define('CARDS_JSON_PATH','/www/wwwroot/ba_sdk/cards.json');
#   define('SDK_LOG_PATH','/www/wwwroot/ba_sdk/sdk.log');
chmod 640 /www/wwwroot/ba_cardadmin/config.php
```

```bash
# 5) 建管理员（哈希规则 = bcrypt(hmac_sha256(密码, salt))，与 inc/auth.php 一致）
cd /www/wwwroot/ba_cardadmin
php -r '$s=bin2hex(random_bytes(16)); echo $s,"\n",password_hash(hash_hmac("sha256","<管理员口令>",$s),PASSWORD_BCRYPT),"\n";'
# 把上面两行输出（salt / hash）填进下面 SQL，注意用带引号的 heredoc，避免 $ 被 shell 展开
mysql -uroot -p ba_cardadmin <<'SQL'
INSERT INTO admins (username, pass_hash, salt, enabled)
VALUES ('<管理员用户名>', '<上一步的 hash>', '<上一步的 salt>', 1);
SQL

# 6) 安装锁 + 权限（.user.ini 的 open_basedir 也要跟着改）
cat > /www/wwwroot/ba_cardadmin/installed.lock <<'JSON'
{"installed_at":"<YYYY-MM-DD HH:MM:SS>","php":"8.2","db_host":"127.0.0.1","db_port":3306,
 "db_name":"ba_cardadmin","admin_user":"<管理员用户名>",
 "cards_json_path":"/www/wwwroot/ba_sdk/cards.json","sdk_log_path":"/www/wwwroot/ba_sdk/sdk.log"}
JSON
printf 'open_basedir=/www/wwwroot/ba_cardadmin/:/tmp/:/www/wwwroot/ba_sdk/:/www/wwwroot/bapatch/\n' > /www/wwwroot/ba_cardadmin/.user.ini
chown -R www:www /www/wwwroot/ba_cardadmin
chmod -R 755 /www/wwwroot/ba_cardadmin
mkdir -p /www/wwwroot/ba_cardadmin/logs /www/wwwroot/ba_cardadmin/state && chown -R www:www /www/wwwroot/ba_cardadmin/logs /www/wwwroot/ba_cardadmin/state
```

**语法检查 + nginx 站点**：

```bash
find /www/wwwroot/ba_cardadmin -name '*.php' -print0 | xargs -0 -n1 php -l | grep -v 'No syntax errors' || echo 'ALL PHP OK'

cat > /etc/nginx/conf.d/ba-panel.conf <<'NGINX'
server {
    listen 8081;
    server_name _;
    root /www/wwwroot/ba_cardadmin;
    index index.php index.html;
    client_max_body_size 8m;
    autoindex off;

    # 敏感文件与内部目录一律挡掉（与包内 nginx.conf.example 同义）
    location ~* ^/(config\.php|config\.php\.example|installed\.lock|README\.md)$ { deny all; return 403; }
    location ~* \.(sql|log|bak|old|orig|swp|tmp|md)$ { deny all; return 403; }
    location ~ /\. { deny all; return 403; }
    location ^~ /inc/   { deny all; return 403; }
    location ^~ /cron/  { deny all; return 403; }
    location ^~ /sql/   { deny all; return 403; }
    location ^~ /state/ { deny all; return 403; }
    location ^~ /logs/  { deny all; return 403; }

    location / { try_files $uri $uri/ /index.php?$query_string; }
    location ~ \.php$ {
        include fastcgi_params;
        fastcgi_pass unix:/tmp/php-cgi-82.sock;   # ← 按你的 PHP-FPM socket 改
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    }
}
NGINX
nginx -t && systemctl reload nginx

curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8081/login.php          # 200
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8081/pages/items.php     # 302（跳登录）
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8081/config.php          # 403
```

**页面验收**：浏览器打开 `http://<服务器IP>:8081/login.php`，用上一步的管理员登录 → 仪表盘能开 → 左侧能看到「卡密 / 玩家 / 抽卡概率 / 道具（GM）/ 设置」；「抽卡概率」页能读出 4 组阈值（它调 `GET /api/admin/gacha/rates`），说明 `BA_ADMIN_KEY` 填对了。

### 3.9 第 9 步：客户端打补丁（改 `SDKConfigSettings.json` 的 `sdk_url` + state 地址 + 重签名）

在**构建机**（Windows/Linux 都行）上做，不要拿服务器跑（要 8 GB 磁盘、2 GB 内存）：

```bash
# 0) 依赖：Python 3.12 + openssl 在 PATH；原版 APK ~2.13 GB
python3 -V && openssl version

# 1) 生成你自己的签名密钥（口令/别名自己定；包内 ba_private.keystore 是出包环境的，不要用）
python3 /root/ba_pkg/client/noroot/build_noroot_apk.py --gen-keystore /root/BA_client_<年份>.keystore

# 2) 打补丁（一条命令同时改 sdk_url 与 state 入口，并重签 v1+v2+v3）
python3 /root/ba_pkg/client/noroot/build_noroot_apk.py \
  --src /root/cn_base_3.0.2.apk \
  --out /root/BA_<SERVER_DOMAIN>_<日期>.apk \
  --sdk-url https://sdk.<SERVER_DOMAIN> \
  --gmconfig-url <SERVER_DOMAIN> \
  --keystore /root/BA_client_<年份>.keystore --storepass <KEYSTORE_PASS> --alias ba

# 3) 校验产物（v1/v2/v3 + GameMainConfig + sdk_url）
python3 /root/ba_pkg/client/noroot/build_noroot_apk.py --verify-only /root/BA_<SERVER_DOMAIN>_<日期>.apk --gmconfig-url <SERVER_DOMAIN>
```

参数含义：

| 参数 | 改的是什么 | 说明 |
|---|---|---|
| `--sdk-url` | `assets/SDKConfigSettings.json` 的 `sdk_url` | 指向你的 SDK 站点；**必须 https + 真证书** |
| `--gmconfig-url` | `assets/bin/Data/<hash>` 里的 `GameMainConfig.ServerInfoDataUrl` | 默认展开成 `http://state-api.<域名>/api/state` + `http://stateqc-api.<域名>/api/state`；想走 TLS 加 `--gmconfig-scheme https` |
| `--keystore / --storepass / --alias` | 重签名用的密钥 | 用你自己的（第 1 步生成） |
| `--asset-replace NAME=PATH` | 通用资源替换（可多次） | `--rename-package` 改包名仅用于与原包共存，一般**不要**改 |

**为什么必须重签名**（三条，缺一条都装不上或进不去）：

1. **改过的 APK 原签名必然失效**——zip 里任何字节一变，v1 `MANIFEST.MF` 摘要与 v2/v3 的签名块全对不上，Android 直接判签名不一致（`INSTALL_PARSE_FAILED_INCONSISTENT_CERTIFICATES` / `INSTALL_FAILED_UPDATE_INCOMPATIBLE`）。
2. **v1 / v2 / v3 必须同时重签且互相一致**——只补 v2/v3 时 Android 7 以下走 v1 会失败；只补 v1 时 7+ 会因「有 v2 块但摘要不符」失败；v1 还要求 `.SF` 带 `X-Android-APK-Signed: 2, 3`。构建器一次重算三层，`--verify-only` 逐层验。
3. **包名+签名共同决定“能不能覆盖安装”**——签名换了，同包名**不能覆盖**，必须先卸载旧包；所以分发说明里要写「先卸载官方客户端再装」。

**装包验收**：`adb install -r <产物>.apk`（或手机直接点）→ 能装、能启动到登录页 → 输入卡密能过 SDK 登录。

### 3.10 第 10 步：端到端验收（一步不过就停）

1. **登录**：客户端启动 → 输卡密 → 进入标题界面，不再弹「维护中」（`/api/state` 的 `State` 必须是 `0`）。
2. **LoginSync**：进游戏加载进度条正常走完；`/www/wwwroot/bapatch/logs/api_all_requests.log` 里能看到 `loginsync` 记录，响应量级 **58 万–78 万字节**；桥日志里 `ShopRecruits` = **529**。
3. **招募界面**：进入招募面板 → 标题/说明/按钮**不是**红字 `No LocalizeKey`、页签**没有** `DUMMY`、十连按钮**可点**、「注意事项」能打开（对应 §3.5 的 90004）。
4. **抽卡**：抽一次/十连 → 有出货动画、背包里道具增加、青辉石按预期变化（**注意 §7 第 5 条：服务端不校验消耗，公网前必须自己补**）。
5. **GM 一键记忆大厅**：管理站 → 道具页 → 「发放全部记忆大厅」→ 二次确认 → 进游戏查邮箱 → 领取 → 大厅列表出现（258 个，见 §7 第 7 条）。

---

## 4. 补丁逐个说明

| 补丁名 | 作用 | 涉及文件（包内 → 线上） | 怎么加 | 怎么验证 | 回滚 |
|---|---|---|---|---|---|
| **出口道具过滤**（`BAPATCH-EXPORTFILTER v1`） | 服务端日服表是国服客户端的**超集**；下发前把客户端不认识的 `ItemDB.UniqueId` 摘掉，避免整包解析失败（历史上脏 id `90070000` 直接导致登录死循环） | `server/Services/ClientItemFilter.cs`（源码）→ 重编译；`server/Resources/ClientItemIds.txt`（**1,803** 个 id，12,659 B / `48af0fd9…`）→ `/www/wwwroot/ba_srv/Resources/` | 用包内 DLL 即为已启用；重编译则拷 `ClientItemFilter.cs` 进源码 + 按 `EXPORT_FILTER.md` 在 `Core/HandlerManager.cs` 的 `Dispatch` 加钩子 | 启动日志 `loaded 1803 client item id(s) … item export filter is ON`；`/api/item/list` 返回的道具 id 全在名单内 | 清空/改名 `Resources/ClientItemIds.txt` 即**自动关闭**（fail-open）；或还原旧 DLL |
| **响应壳对齐官方**（`BAPATCH-ENVELOPE v1`） | ① 每条响应都回显 `SessionKey`（官方 109/109 都带）；② `ServerNotification=8`（未读邮件红点）**只在邮件协议 7000–7004** 带，不再污染其它协议 | 编在 `server/Shittim-Server.dll`；源码改动见 `ENVELOPE_ALIGN.md` | 用包内 DLL；重编译按文档改 `ShouldEchoSessionKey` 与 `ServerNotification` 赋值处 | `LoginSync` 的 `ServerNotification` = `None`；`Mail_Check(7001)` 仍 = `8` | 还原旧 DLL |
| **90004 `Management_Data` 结构修复**（`90004-PATCH v1`，**最重要**） | 把桥里「16 键平铺、无 `Data` 外壳、列表全空」的硬编码桩，换成官方 **6 层信封 + `Data` 9 键**；没有它招募界面就是红字 | `bridge/account_auth_probe.py`（已含补丁）；`bridge/patch_90004.py` + `dto90004.py`（重打用）；`bridge_tools/_ba_state/90004_ops.json`（10,883 B / `938ae908…`） | **线上真身已打**，只需 `--verify`；若是新桥则 `patch_90004.py --src <桥路径> --apply` 后重启 | `verify_90004.py` → `RESULT: PASS`；90004 响应 **~14 KB**（坏态 2 KB），`Data` 条数 **7/6/14/12**；真机无红字/无 DUMMY | `patch_90004.py --src <桥路径> --rollback`（自动找最近 `.bak.90004.*`）；删 ops 文件会退回「全空合法形状」=界面坏回去 |
| **抽卡概率可配**（`BAPATCH-P0RATES v1`） | 4 组阈值（Normal/Pickup/Limited/Fes）从 `Data/gacha_rates.defaults.json` 读，管理 API 可改并**热加载**（改完不用重启） | `server/Data/gacha_rates.defaults.json`（312 B / `59bbf27d…`）→ `/www/wwwroot/ba_srv/Data/`；覆盖文件 `Data/gacha_rates.json` 由接口生成；管理页 `panel_full/.../pages/gacha_rates.php` + `inc/gacha.php` | 放 json + 用包内 DLL；面板页随整站复制 | 启动日志 `[GachaRates] boot` 4 行（`ssrThreshold=30/23/23/44`）；`curl -H 'X-Admin-Key: …' http://127.0.0.1:5000/api/admin/gacha/rates` → `ok:true`；`POST` 后 `Data/` 出现 `gacha_rates.json` | `POST /api/admin/gacha/rates/reset {"scope":"all"}`；或删 `Data/gacha_rates.json` + 还原旧 DLL |
| **管理站两个新页**：抽卡概率 + GM 一键记忆大厅 | 看/改 4 组阈值；把**客户端认识的 258 个**记忆大厅做成邮件附件一次发给玩家（幂等） | `pages/gacha_rates.php`、`inc/gacha.php`、`inc/gm_lobby.php`（新增）、`pages/items.php`（覆盖） | 随整站复制即可（已含） | 概率页能读 4 组数值、保存后生效；道具页出现「发放全部记忆大厅」按钮，`php -r 'require ".../inc/gm_lobby.php";'` 自检 258 条 | 删 `inc/gm_lobby.php` + 还原 `pages/items.php` / `pages/gacha_rates.php` |
| **桥：`Item_List(4000)` 中继** | 背包从「桥的 620 B 桩」变成真实数据；4000 不再被桥吸收，走转发 | `bridge_tools/tools/cn_4000.txt` = `0`；桥代码里 `RL2_HANDLED` 不含 4000 | 开关文件放到 `tools/`（本包已含）；改的是代码常量时才需重启桥 | 经桥 `/api/item/list` → 200；道具量级（本项目测试账号 53 件 / 5,016 B） | `echo 1 > tools/cn_4000.txt`（回桩）+ 还原桥 |
| **桥：`Shop_List` 空引用修复** | `CategoryList` 缺省时 `null` 直接 `foreach` 会 NRE → 500 → 客户端重试死循环；改成早退 + `ServerDateTime() ?? Now` | 编在 `server/Shittim-Server.dll`；源码 `Services/ShopManager.cs`（+11/−1），见 `SHOPLIST_NRE_FIX.md` | 用包内 DLL；重编译按文档 diff | 不带 `CategoryList` 请求 → **200 + `ShopInfos: []`**（不再 500）；带 11 分类 → 205,826 B / 1,900 商品 | 还原旧 DLL |

**两条额外说明**

- **90004 与「换期」**：补丁不用再打，但 `90004_ops.json` 的档期会过期（本批到 **2026-11-26 13:59:59**），过期后界面**原样坏回去**且桥**不报错**（读不到就回「列表全空 + 3 个 null」的合法形状）——「文件在不在」必须单独验收。
- **出口过滤拦「出口」不拦「入口」**：库一行不删，可随时关掉过滤器复现问题；但别把客户端不认识的 id 塞进库（§7 第 3 条）。**概率补丁只做了「可配」**，没改「非 custom 路径阈值不累加」的语义，Pickup/Fes 实际出率仍偏低（见 `GACHA_RNG_ANALYSIS.md`）。

---

## 5. 必须自己填的占位符清单

**口径**：本包**已脱敏**，下列位置均为占位符（`<REDACTED_*>`、`<SERVER_IP>`、`<CERT_PATH>`、`example.com` 等），**部署前必须替换为你自己的值**；若本包曾在你自己的环境使用过，**相应口令请轮换**。逐文件逐行的替换清单见包根 `REDACTION.md`。**本文不复述任何原值**（详见 §8）。

| # | 文件 | 字段 | 占位符形态 | 含义 / 要换成什么 |
|---|---|---|---|---|
| 1 | `panel_full/ba_cardadmin/config.php` | `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASS` | `<DB_HOST>` `<DB_PASSWORD>` 等 | 你 §3.8 建的 MySQL 四要素 |
| 2 | 同上 | `APP_SECRET` | `<64位hex>` | `php -r "echo bin2hex(random_bytes(32));"` 生成；**不要留空** |
| 3 | 同上 | `BA_ADMIN_BASE` / `BA_ADMIN_KEY` | `<AdminApiKey>` | 必须与 `/www/wwwroot/ba_srv/Config/Config.json` 的 `ServerConfiguration.AdminApiKey` 一致；服务端配了 key 后**连环回也要带** |
| 4 | 同上 | `CARDS_JSON_PATH` / `SDK_LOG_PATH` | `/www/wwwroot/ba_sdk/...` | 与 §3.7 的实际路径一致（线上脚本默认在 `/root/bapatch/`，是旧路径） |
| 5 | `panel_full/ba_cardadmin/installed.lock` | `admin_user` / 路径 | `<管理员用户名>` | 重新生成或改成本机实际值；它只是标记文件，真正判断在 `config.php` 常量 |
| 6 | `panel_full/ba_cardadmin/.user.ini` | `open_basedir` | `<PANEL_ROOT>` | 换成你的站点根 + `/tmp/` + SDK/桥目录（路径不同不改会 500） |
| 7 | `server_config/systemd/ba-*.service` | `User` / `WorkingDirectory` / `ExecStart` / `StandardOutput` | `<SRV_ROOT>` `<BAPATCH_ROOT>` `<DOTNET_ROOT>` `<RUN_USER>` | 按 §3.3 的表逐项改；日志目录必须先存在 |
| 8 | `server_config/nginx/**`（参考用） | `server_name` / `ssl_certificate*` / `alias` | `<SERVER_DOMAIN>` `<CERT_PATH>` | 你的域名与真证书路径；**别整目录覆盖** |
| 9 | 自建 `/www/wwwroot/_ba_state/state-api/api-state.json` | `Servers[]` | `http://gs-api.<SERVER_DOMAIN>/api/` | 客户端后续 `/api/*` 的根；协议要与 vhost 对得上 |
| 10 | `/www/wwwroot/ba_sdk/resp/common_config.json` | `DetectionAddress.HTTP/MTR`、`Internet` | `<SERVER_DOMAIN>` | 检测地址指自己的 `/api/health`，否则客户端判定「连不上服务器」 |
| 11 | 同上 | `SLS.AccessKeyID/Secret`、`Captcha.AppID`、`Udata.*`、`WechatAppID`、`OneKeyLoginSecret` | 出包环境的第三方 key | **没有对应账号就关掉**（`ENABLE=false` / `Enable=false` / 置空），别把别人的 key 发到公网 |
| 12 | `/www/wwwroot/ba_sdk/cards.json` | 卡密键与 `devices/expire/bind_one` | `<第一张卡密>` | 自己造卡；正式运营用管理站生成 |
| 13 | `client/noroot/ba_private.keystore` | `storepass` / `alias` | `<KEYSTORE_PASS>` | 出包环境的签名密钥；**用 `--gen-keystore` 生成自己的**，否则别人能签同名包冒充你 |
| 14 | `client/noroot/build_noroot_apk.py` 命令行 | `--sdk-url` / `--gmconfig-url` | `<SERVER_DOMAIN>` / `https://sdk.<SERVER_DOMAIN>` | 客户端唯一“知道服务器在哪”的两处 |
| 15 | `bridge/**` 与 `bridge_tools/tools/*.py` | 硬编码 `/www/wwwroot/bapatch/...`（日志、开关、`_ba_state`、`accounts.db`） | `<BAPATCH_ROOT>` | **默认就用这个路径**；换目录必须全局替换，否则桥读不到开关（行为静默变化，§7 第 1 条） |
| 16 | `bridge_tools/cn_*.txt`（27+3 个） | 开关值（`bridge`/`forward`、`0`/`1`…） | — | 保持包内值即可；只有 `cn_bridge_mode.txt` 必须是 `bridge` |
| 17 | 各文件里的占位形态 | `<REDACTED_*>`、`<SERVER_IP>`、`example.com` | 同上 | 见到就替换；若发现**真实**域名/IP/口令，按 §8 当泄露处理并轮换 |
| 18 | `/www/wwwroot/ba_sdk/pay.json` | `PayState`/`DeliveryState`/`Amount` | — | 不做支付就保持 `2/2/3000`（关）；要做支付自己接 |

---

## 6. 验收清单（勾选式，带命令与期望值）

### 6.1 服务端（机器可核对，先跑这些）

- [ ] **三个服务在跑**：`systemctl is-active ba-shittim ba-sdk ba-bridge` → `active active active`
- [ ] **四个端口在听**：`ss -lntp | grep -E ':(5000|5100|9097|8080)\b'` → 4 行
- [ ] **桥的 cwd 正确**：`readlink /proc/$(systemctl show -p MainPID --value ba-bridge)/cwd` → `/www/wwwroot/bapatch/tools`
- [ ] **桥单实例**：`pgrep -fc account_auth_probe.py` → `1`（>1 必须杀掉多余的）
- [ ] **桥活着**：`curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9097/` → `200`
- [ ] **服务端健康**：`curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5000/health` → `200`（服务端原生端点是 `/health`；`/api/health` 是 §3.6 给客户端探活的 nginx 端点）
- [ ] **DLL 是指定版本**：`sha256sum /www/wwwroot/ba_srv/Shittim-Server.dll` → `c013f4427ad01d44c00cc63af3de817b800638fcd8ec0ee55de41126aed106aa`
- [ ] **卡池 529**：`grep -c '"Id"' /www/wwwroot/ba_srv/Data/GachaRecruitBanners.cn.json` → `529`
- [ ] **出口过滤生效**：`grep -E 'loaded 1803 client item id' /var/log/ba-shittim.log | tail -1` → 有输出
- [ ] **90004 结构 PASS**：`cd /www/wwwroot/bapatch/tools && python3 verify_90004.py` → `RESULT: PASS`，响应 **~14,016 B**，`Data` = **7/6/14/12**，31 项 `FAIL=0`；体积只有 ~2 KB = 未生效（回 §3.5）
- [ ] **概率接口**：`curl -s -H 'X-Admin-Key: <AdminApiKey>' http://127.0.0.1:5000/api/admin/gacha/rates | head -c 200` → `{"ok":true,...}`
- [ ] **`/api/state`**：`curl -s http://127.0.0.1/api/state` → 含 `"State":0` 与你的 `gs-api` 地址
- [ ] **`/api/health`**：`curl -s -H 'Host: gs-api.<SERVER_DOMAIN>' http://127.0.0.1/api/health` → `ok`（2 字节）
- [ ] **管理 API 未暴露**：`curl -s -o /dev/null -w '%{http_code}' -H 'Host: gs-api.<SERVER_DOMAIN>' http://127.0.0.1/api/admin/status` → `404`
- [ ] **SDK 配置可取**：`curl -s http://127.0.0.1:8080/common/config | head -c 80` → JSON
- [ ] **管理站登录页**：`curl -o /dev/null -w '%{http_code}' http://127.0.0.1:8081/login.php` → `200`；`/pages/items.php` → `302`；`/config.php` → `403`
- [ ] **面板 PHP 语法**：`find /www/wwwroot/ba_cardadmin -name '*.php' -print0 | xargs -0 -n1 php -l | grep -v 'No syntax errors'` → 无输出
- [ ] **两个库存在**：`python3 -c "import json;print(len(json.load(open('/www/wwwroot/ba_sdk/cards.json'))['cards']))"` → ≥1；`python3 /www/wwwroot/bapatch/tools/account_service.py --stats --db /www/wwwroot/bapatch/data/accounts.db` → 有输出（登录后 accounts 才非空；`LoginSync` 体积与 `ShopRecruits=529` 见 §3.10 第 2 条）

### 6.2 一条命令跑完（存成 `/root/check_all.sh`）

```bash
#!/usr/bin/env bash
# 用法：bash /root/check_all.sh ; 退出码 0 = 全过
API_HOST="gs-api.<SERVER_DOMAIN>"; ADMIN_KEY="<AdminApiKey>"
fail=0; ok(){ echo "  OK   $1"; }; ng(){ echo "  FAIL $1"; fail=1; }
chk(){ [ "$2" = "$3" ] && ok "$1 ($2)" || ng "$1 期望[$3] 实际[$2]"; }
chk  "shittim"   "$(systemctl is-active ba-shittim)" active
chk  "sdk"       "$(systemctl is-active ba-sdk)"     active
chk  "bridge"    "$(systemctl is-active ba-bridge)"  active
chk  "bridge实例" "$(pgrep -fc account_auth_probe.py)" 1
chk  "bridgeHTTP" "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9097/)" 200
chk  "srvHTTP"    "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5000/health)" 200
chk  "state"      "$(curl -s http://127.0.0.1/api/state | grep -c '\"State\":0')" 1
chk  "health"     "$(curl -s -H "Host: $API_HOST" http://127.0.0.1/api/health)" "ok"
chk  "admin屏蔽"  "$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $API_HOST" http://127.0.0.1/api/admin/status)" 404
chk  "banners"    "$(grep -c '\"Id\"' /www/wwwroot/ba_srv/Data/GachaRecruitBanners.cn.json)" 529
chk  "rates"      "$(curl -s -H "X-Admin-Key: $ADMIN_KEY" http://127.0.0.1:5000/api/admin/gacha/rates | grep -c '\"ok\":true')" 1
chk  "panel登录"  "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8081/login.php)" 200
( cd /www/wwwroot/bapatch/tools && python3 verify_90004.py | tail -3 ) || fail=1
if [ $fail -eq 0 ]; then echo "ALL CHECKS PASSED"; else echo "SOME CHECKS FAILED"; fi; exit $fail
```

### 6.3 客户端（人眼，唯一权威）

- [ ] 登录页出现、输卡密能过（SDK 200）；标题界面不显示「维护中」
- [ ] 进游戏不出现「同步账号信息时发生错误」/不死循环重登
- [ ] 招募界面：**无红字 `No LocalizeKey`**、**无 `DUMMY` 页签**、十连按钮**可点**、「注意事项」**能打开**
- [ ] 抽卡有出货、背包含新道具、货币变化合理（消耗校验见 §7 第 5 条）
- [ ] 管理站 GM「发放全部记忆大厅」→ 邮件到达 → 领取 → 大厅列表出现

---

## 7. 已知的坑（都是我们实际踩过的：症状 → 原因 → 解法）

**1. 桥重启必须在 `tools` 目录里**
- 症状：进程起来了、端口在听，但回包不对/直接崩，或改了开关毫无反应 ｜ 原因：桥用 **cwd 相对路径** import 同目录模块（`cn_cipher`/`cn_wire`/`genNNNN`），并在「脚本目录 → `/www/wwwroot/bapatch/`」两处找 `cn_*.txt` ｜ 解法：只用 systemd 起（`WorkingDirectory` 已保证），别再手工 `nohup`；换目录后用 `readlink /proc/<pid>/cwd` 复核。

**2. 90004 少了 `Data` 外壳 → 招募界面整层红字**
- 症状：标题/说明/点数说明/底部按钮全显示 `[FF0000]No LocalizeKey`，页签是 `DUMMY`，十连按钮点了**连本地提示都没有** ｜ 原因：桥把 90004 写成 16 键平铺、无 `Data`、列表全空，客户端拿不到公告/横幅/概率公示这层数据 ｜ 解法：§3.5；判定标准 `verify_90004.py` → `RESULT: PASS` 且体积 ~14 KB，只有 2 KB 就是没生效。

**3. 往客户端塞它不认识的 id（道具/角色/记忆大厅）→ 登录失败或渲染异常**
- 症状：登录卡在「同步账号信息时发生错误」，2 秒一轮死循环；或抽到角色但立绘/详情空白 ｜ 原因：服务端是**日服表（超集）**、客户端是**国服表**，`ItemDBSchema` 里没有的 id 会让客户端**整包解析失败**（历史案例 `UniqueId=90070000`）｜ 解法：只用 `Resources/Client*.txt` 白名单里的 id；脏数据从库里清掉；出口过滤器只是兜底，不是许可证。

**4. `Shop_List` 的 `CategoryList` 为空会 NRE**
- 症状：某次进商店/招募 `/api/shop/list` 500，客户端反复重试 ｜ 原因：`CategoryList` 可空，字段缺省时反序列化成 `null` 而非 `[]`，旧代码直接 `foreach` ｜ 解法：用包内 DLL（已修），自编就按 `SHOPLIST_NRE_FIX.md` 加 `reqCategoryList == null` 早退；验收标准「不带 `CategoryList` → 200 + `ShopInfos: []`」。

**5. 抽卡消耗服务端不校验（已知漏洞，公网前必须自己补）**
- 症状：改包可以免费十连；`Amount` 传大值一次抽上千次也照出 ｜ 原因：`ShopManager.cs` 里 `req.Cost == null` 时**完全不扣还照出**，其余情况只按 `Amount/120` 算次数、不与 `ShopExcel` 价目比对 ｜ 解法：本项目**未修**（用户拍板暂不做）；公网部署前必须自己做「服务端价目 + 余额校验 + 事务扣减」，否则等于开放无限抽卡。

**6. 客户端 `logcat` 在 release 包不写日志**
- 症状：`adb logcat` 抓 58 MB，游戏进程命中 **0 行** ｜ 原因：release 包不写 Unity 日志 ｜ 解法：别指望日志；只能靠真机人眼 + 服务端/桥日志（`bapatch/logs/api_all_requests.log`、`ba_srv/logs/`）+ 反编译/内存取证。

**7. 记忆大厅只能走邮件包裹，改 `MemoryLobbyUniqueId` 只改「当前选中」**
- 症状：直接更新 `Accounts.MemoryLobbyUniqueId` 后大厅列表**没有新增**，只是选中项变了 ｜ 原因：大厅是「持有物」，必须通过 `ParcelType.MemoryLobby(8)` 的邮件包裹发放 ｜ 解法：用管理站「发放全部记忆大厅」（`POST /api/admin/mail/send`）；幂等，重复点只多几封邮件。

**8. `Type` 必须是字符串 `"MemoryLobby"`，写数字 `8` 会 400**
- 症状：发信接口 400 / 参数错误 ｜ 原因：DTO 的 `Type` 是枚举**字符串**，数字不被接受（落库后内部 `Key.Type` 才是 8）｜ 解法：请求体写 `"Type":"MemoryLobby"`；可一封邮件挂多个包裹（实测 258 个一次成功，1000 个也 200）。

**9. 端口就绪必须轮询，不能 `sleep 3` 后断言**
- 症状：脚本偶尔假失败，或白等 10 秒 ｜ 原因：就绪时间波动大——桥 1,010–1,033 ms，Shittim 5000+5100 **6,141–8,151 ms** ｜ 解法：用 §3.2/§3.3 的轮询片段（`for i in $(seq 1 30); do …; sleep 1; done`）。

**10. 1.6 GB 内存 + `vm.swappiness=0` → 随时 OOM**
- 症状：整机重启后只有手工启动的服务没回来，`journalctl` 里连 OOM 记录都查不到 ｜ 原因：`dotnet` ~200 MB + MySQL ~190 MB + nginx/面板吃满物理内存，`swappiness=0` 让 1 GB swap 几乎不参与 ｜ 解法：**内存 ≥ 2 GB**；加 swap 并把 `vm.swappiness` 调到 10–60；保留单元里的 `DOTNET_GCHeapHardLimit=0x40000000`；所有服务都 systemd 托管。

**11. nginx 全 200 ≠ 服务端没报错**
- 症状：抓包全是 200，但功能不对 ｜ 原因：Shittim 报错时桥会**回落到固定大小桩包**（日志 `relay2_ft=session-retry-failed`），客户端仍收 200 ｜ 解法：看桥日志的 `gen_kind`/`relay2_ft`，以及「恒定体积」特征（如 `contentsave/get` 恒 600 B、`academy/getinfo` 1,772 B）。

**12. 90004 档期会过期（本批到 2026-11-26 13:59:59）**
- 症状：换期后客户端拿到新池子，招募界面又变红 ｜ 原因：`90004_ops.json` 里的公告/活动/公示页带 `EndDate`，且新分支读不到文件时**不报错**、只是列表全空 ｜ 解法：换期只替换这个 json + 重启桥；数据来源优先级：官方抓包 > 用客户端表生成骨架 > 手写占位（见 `GACHA_ROOTCAUSE_90004_FINAL.md` §4.3）。

**13. Excel 表：首次下载 / 自备表二选一，别混**
- 症状：启动卡在 `[Resource Manager] Checking Excel tables...`；或表版本与客户端对不上（抽到不存在的角色）｜ 原因：默认 `DownloadExcelTables: true`、`UseCustomExcel: false`，首次必须出网；自备 `Resources/Dumped/ExcelDB.db` 时要改 `UseCustomExcel: true` ｜ 解法：给出网或先手工放表；确认 `Resources/Dumped` 非空；**别把日服表当国服表**。

**14. 重编译丢了 `Config/GatewayPrivateKey.pem`**
- 症状：客户端卡在「Unpacking game resources」，网关 `50001` 握手失败 ｜ 原因：网关 RSA 公私钥对必须**跨构建保持同一对**，丢了就解不开客户端请求 ｜ 解法：源码仓库里保留 `Shittim-Server/config/Gateway*.pem`，publish 后 `cp -n` 补到 `/www/wwwroot/ba_srv/Config/`，**不要重新生成**。

**15. 换了签名不能覆盖安装**
- 症状：`adb install -r` 报 `INSTALL_FAILED_UPDATE_INCOMPATIBLE` ｜ 原因：Android 用「包名 + 签名」判同源，你重签后就不是同一个应用 ｜ 解法：先卸载官方客户端再装；发版说明里写清。

**16. 管理 API 配了 key 后，连本机也要带 `X-Admin-Key`**
- 症状：面板所有 GM 功能 403，`curl 127.0.0.1:5000/api/admin/status` 也 403 ｜ 原因：`AdminAuthAttribute` 在「配了 key」时**环回不豁免**（反代会让所有请求看起来像 127.0.0.1）｜ 解法：面板 `BA_ADMIN_KEY` 必须等于 `Config.json` 的 `AdminApiKey`；不要用「不配 key」来绕过。

**17. `open_basedir` 没改 → 面板空白/500**
- 症状：管理站 500，`php_82_error.log` 里 `open_basedir restriction in effect` ｜ 原因：包内 `.user.ini` 的 `open_basedir` 是出包环境路径 ｜ 解法：改成你的站点根 + `/tmp/` + SDK/桥目录，然后 `systemctl reload php-fpm-82`。

## 8. 安全提醒（部署前请先读完这节）

### 8.1 凭据

- **本包已脱敏**：`panel_full/ba_cardadmin/config.php`（DB 口令、`APP_SECRET`）、`server_config/nginx/**`（域名/证书路径）、`server_config/bapatch_root/**`、`server_config/ba_sdk/**`、`bridge_tools/**` 里的真实值已全部换成 `<REDACTED_*>` 占位符（**293 个文件 / 1,941 处 / 1,739 行**，逐条见包根 `REDACTION.md`）。**但仍一律当占位符处理**：全换成你自己的，并**轮换所有旧口令/密钥**（DB、`APP_SECRET`、`AdminApiKey`、卡密、签名密钥）；`client/noroot/ba_private.keystore` 是**二进制签名密钥**，未做（也不应做）文本脱敏，**必须换成你自己生成的**。
- 部署完把 `/root/ba_pkg`（含上述文件）删掉或在离线机器上保管；`config.php` 权限 `640`、属主 `www`；不要把 `.bak`/`installed.lock`/`sql/` 暴露到 web（§3.8 的 nginx 规则已挡）。

### 8.2 上游服务端本身的共性缺陷（**公网开放前必须自己加固**）

| 缺陷 | 后果 | 加固方向 |
|---|---|---|
| **没有 token 校验**：`/api/*` 的会话靠请求体里的 `SessionKey`，服务端不做来源/签名校验 | 拿到一个 token 就能冒充；直接打 5000 甚至不需要 token（`BypassAuthentication` 默认 false，但桥这层是唯一闸门） | 5000/5100 **只监听 127.0.0.1**（或用防火墙 DROP），所有入口只留 nginx→9097 |
| **没有请求大小 / 解压上限**（上游用 `ExtractAll` 解 zip） | 大包打爆内存；zip bomb | 在 nginx 设 `client_max_body_size`；服务端侧加解压前尺寸校验；监控内存 |
| **管理 API 无权限分级**（`/api/admin/*` 一把钥匙通吃，无审计分级） | 钥匙一泄露 = 服务器交出去（改货币、删号、发邮件、执行控制台命令） | 见 §8.3：不对外暴露 + 强 key + 单独网段 |
| **无频率限制** | 爆破卡密、刷接口 | nginx `limit_req`；SDK 侧登录失败锁定（管理站有 `LOGIN_MAX_FAIL=5`，SDK 侧自行确认） |

### 8.3 上线前最小加固清单（照做）

```bash
ss -lntp | grep -E ':(5000|5100|9097|8080)\b'     # 1) 都应显示 127.0.0.1（只监听环回）

# 2) 防火墙只放 22 / 80 / 443（8081 只放你的办公 IP）
firewall-cmd --permanent --add-service=http --add-service=https
firewall-cmd --permanent --add-rich-rule='rule family=ipv4 source address=<你的办公IP> port port=8081 protocol=tcp accept'
firewall-cmd --reload

# 3) 管理 API 在公网 vhost 上必须 404（§3.6 已配）
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: gs-api.<SERVER_DOMAIN>' http://127.0.0.1/api/admin/status   # 404

# 4) 强 key：AdminApiKey / APP_SECRET / DB 口令 全部 32+ 随机字符，且互不相同
python3 -c "import secrets;print(secrets.token_hex(32))"

# 5) 限速：nginx http{} 里 limit_req_zone $binary_remote_addr zone=ba:10m rate=20r/s;
#    /api/ location 里 limit_req zone=ba burst=40 nodelay;
# 6) 清理不该暴露的备份/静态文件
ls /www/wwwroot/ba_srv/*.json /www/wwwroot/ba_cardadmin/*.bak* 2>/dev/null   # 有就清
```

> 最后一句实话：**这套东西的上游服务端设计目标是"自己玩"**，不是公网多租户。要做公开运营，除了上面这些，还得补：抽卡消耗校验（§7 第 5 条）、管理操作审计、卡密防爆破、备份与回滚演练、以及**你自己对合规与授权范围的确认**。这些本包都不替你解决。

---
*文档版本：20261120 · 对应交付包 `BA_自研补丁_20261120.zip`。文中所有路径以 §2 规划为准，包内布局以 `MANIFEST.txt` 为准。*
