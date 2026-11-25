# P0 改造前：全量备份 + 只读快照

- 时间：2026-11-19 02:35–02:37（Asia/Shanghai）｜ 执行：srv-ops
- 性质：**只读 + 备份**（未 restart 任何服务、未改任何配置、未部署）
- 目的：为接下来的「抽卡概率可配置化（C# 服务端 + 管理站面板）」准备完整回滚点

---

## 1. 备份目录

```
/root/PRE_P0_20261119_023546/          总大小 666 MB
├── shittim_ba_srv.tgz        688,655,811 B   (657 MB，/www/wwwroot/ba_srv，**排除 logs/**)
├── panel_ba_cardadmin.tgz        228,293 B   (224 KB，管理站整站)
├── bridge_bapatch_conf.tgz        68,429 B   (68 KB，桥 + _ba_state + 33 个开关文件)
├── nginx_conf.tgz                  6,497 B   (nginx 主配置 + 面板 vhost 快照，仅供参考)
├── MANIFEST.txt                    6,278 B   (81 行，含每项大小/sha256/开关值/服务状态)
├── RESTORE.md                      4,098 B   (76 行，逐条恢复命令)
└── singles/                                   (关键单文件，便于秒级回滚)
      Shittim-Server.dll      2,688,000 B
      Schale.dll              5,392,896 B
      appsettings.json              460 B
      appsettings.Local.json        159 B
      Config.json                 2,688 B
      GachaRecruitBanners.cn.json 40,739 B
      ClientItemIds.txt          12,659 B
      account_auth_probe.py     228,775 B
      90004_ops.json             10,883 B
      bans.inc.php              107,659 B
      bans.page.php              60,571 B
```

**MANIFEST.txt 摘要（4 个包）**
```
FILE                              BYTES            SHA256
shittim_ba_srv.tgz               688,655,811      见 MANIFEST 第 2 节
panel_ba_cardadmin.tgz             228,293        …
bridge_bapatch_conf.tgz             68,429        5cf913587e8cf998cb516e65d826f64e10bbff25e618cd6d88a5c8c53ef333ec
nginx_conf.tgz                       6,497        …
```

## 2. 打包内容明细

| 包 | 覆盖范围 | 备注 |
|---|---|---|
| `shittim_ba_srv.tgz` | `/www/wwwroot/ba_srv` 全部内容（`Shittim-Server.dll`、`Schale.dll`、`Data/`、`Resources/`（含 `ClientItemIds.txt`、`Dumped/`、`Downloaded/`）、`Config/`、`config/`、`appsettings*.json`、`runtimes/`…） | **排除 `logs/`（98 MB）** 以控制体积；含私钥，注意保密 |
| `panel_ba_cardadmin.tgz` | 管理站整站（93 个文件 / 2.8 MB），含 `pages/bans.php`、`inc/bans.php` 等主树缺失文件 | 完整快照 |
| `bridge_bapatch_conf.tgz` | `tools/account_auth_probe.py` + `_ba_state/`（含 `90004_ops.json`）+ **29 个 `cn_*.txt`（bapatch 根）+ 3 个 `tools/cn_*.txt`** | 共 33 个条目 |
| `nginx_conf.tgz` | `nginx.conf` + `/www/server/panel/vhost/nginx/*.conf` | **只读导出，不要整目录覆盖** |

## 3. 本地快照（拉到 Windows 工作区）

```
work\ba\srv_live\P0_SNAPSHOT_20261119_023658\
├── Shittim-Server\
│     Shittim-Server.dll      2,688,000 B   sha256 160c3e159956ee8300b57a90af70bc8813cb03ce5aef48d3c36615631cf4bd16
│     Schale.dll              5,392,896 B   sha256 b06f46090f9d8eb8657e51401b789178d9090ad5a5a6d6d1faaa791dad429858
│     appsettings.json              460 B
│     appsettings.Local.json        159 B
│     Data\                    （GachaRecruitBanners.cn.json 40,739 B + Excel/Koyuki/ProhibitedWord）
│     config\                  （ba_version_cache.json）
│     Config\                  （Config.json / sessions.json / 网关证书 pem / ServerInfoConfig.json）
├── panel\                     **整站 90 个文件**（含 pages\bans.php、inc\bans.php、inc\players.php、inc\sync.php…）
└── SHA256SUMS.txt             （109 个文件的 sha256 + 字节数清单）
```

统计：**109 个文件 / 11,006,543 B**（Shittim 关键文件 + 配置 + 整站面板）。
本地清单文件：`work\ba\srv_live\P0_SNAPSHOT_20261119_023658\SHA256SUMS.txt`

> 注：`Config/` 里的 `GatewayPrivateKey*.pem` 与 `Config.json`（含 AdminApiKey）已随快照落到本地 —— 属于敏感文件，勿外传。

## 4. RESTORE.md（恢复指南）

```
/root/PRE_P0_20261119_023546/RESTORE.md      （76 行，逐条命令）
```
内容包含：
1. 恢复前必读（三个包各自覆盖什么、解压到哪）
2. 恢复 Shittim 整目录（stop → tar -x → start → 端口轮询 → 校验两个 DLL 的 sha256）
3. **只回滚 DLL**（最快路径：`cp singles/Shittim-Server.dll` + `Schale.dll` → restart）
4. 恢复管理站（tar → 处理 `.user.ini` 的 `chattr -i/+i` → `systemctl reload php-fpm-82` → 302 验证）
5. 恢复桥 + 开关 + ops（解 tar → kill → `cd tools && umask 007` 重启 → 轮询 9097 → 校验 md5/ops sha256）
6. 恢复后验证清单（服务、端口、`/api/item/list`、日志无 ERR）
7. 注意事项（不含 logs、nginx 包仅参考、备份含私钥）

---

## 5. 环境事实（部署面板/服务端时需要）

| 项 | 实际值 |
|---|---|
| **Shittim 工作目录** | **`/www/wwwroot/ba_srv`**（`WorkingDirectory` 与 `/proc/<pid>/cwd` 实测一致） |
| Shittim 启动 | `tmux new-session -d -s shittim … "/root/dotnet10/dotnet /www/wwwroot/ba_srv/Shittim-Server.dll --console --id 2"` |
| **管理站站点根** | **`/www/wwwroot/ba_cardadmin`**（`nginx -T` 里 `server_name <SERVER_IP>` 的 `root`） |
| 管理站规模 | 93 个文件 / 2.8 MB |
| **php-fpm** | **PHP 8.2.31（NTS）**，服务名 **`php-fpm-82`**（另有 81/83/84/85 在跑） |
| php-fpm pool | `/www/server/php/82/etc/php-fpm.d/` 下只有 `www.conf.default`（pool 定义在 `php-fpm.conf` 的 include 里，实际 pool 名 `www`） |
| **open_basedir（实际）** | `php -i` 显示 **`no value`**（php.ini 未设）；**面板用 `.user.ini` 生效**：<br>`open_basedir=/www/wwwroot/ba_cardadmin/:/tmp/:/www/wwwroot/ba_sdk/:/www/wwwroot/bapatch/` |
| 面板 `.user.ini` 注意 | 带**不可变属性**（`chattr +i`），改它必须先 `chattr -i`，改完再 `chattr +i` |
| nginx 配置位置 | 主：`/www/server/nginx/conf/nginx.conf`；站点：`/www/server/panel/vhost/nginx/*.conf`（含 `<SERVER_IP>.conf`、`ba_mitm.conf`、`free_waf.conf` 等） |

其它已在跑的服务：
```
ba-shittim: active（5000/5100）
桥 9097: pid 见 MANIFEST（实例数 1）
sdk 8080: active
php-fpm-82: active
```

---

## 6. 旧 `custom_rates` 残留检查（P0 关键）

### 6.1 `/www/wwwroot/gacha_config.json`
```
$ ls -la /www/wwwroot/gacha_config.json
ls: cannot access '/www/wwwroot/gacha_config.json': No such file or directory

$ find /www/wwwroot -maxdepth 3 -name 'gacha_config.json'
（无输出）

⇒ **文件不存在**，没有 `custom_rates`，不会覆盖新加的配置通道。
```

### 6.2 Shittim 目录里的 gacha 相关配置
```
$ find /www/wwwroot/ba_srv -maxdepth 3 \( -name '*gacha*config*' -o -name 'gacha_rates*' -o -name '*gacha*.json' \)
（无输出，除下面这个卡池清单）
$ ls -l /www/wwwroot/ba_srv/Data/*.json
-rw-r--r-- 1 root root 40739 Nov 18 22:24 /www/wwwroot/ba_srv/Data/GachaRecruitBanners.cn.json
```
⇒ 只有一个卡池清单 JSON，**没有任何 gacha 概率配置文件**。

### 6.3 管理接口 `GET /api/admin/gacha/config`（只读，未 POST）
```
AdminApiKey：从 /www/wwwroot/ba_srv/Config/Config.json 的 ServerConfiguration.AdminApiKey 取到（64 字符，不在报告中明文）

$ curl -s -H "X-Admin-Key: ***" http://127.0.0.1:5000/api/admin/gacha/config
HTTP **200**   95 B

返回体（全文）：
{"path":"/www/wwwroot/gacha_config.json","exists":false,"ssr":0,"sr":0,"r":0,"guaranteed":null}

键结构：
  path        : str   （= /www/wwwroot/gacha_config.json）
  exists      : bool  （= false）
  ssr         : int   （= 0）
  sr          : int   （= 0）
  r           : int   （= 0）
  guaranteed  : null  （null）
```
⇒ 接口本身**存在且可用**，明确报告 `exists:false`，即当前**没有任何外部概率覆盖配置**。

### 6.4 结论（给 P0 实现）
1. 外部覆盖通道（`GachaCommand.cs` 读 `/www/wwwroot/gacha_config.json`、5 秒 TTL）**当前处于"无文件"状态**，
   所以新配置不会被它覆盖 —— **但它是"文件一旦出现就整体覆盖"的语义**，P0 上线时要：
   - 明确新配置的权威优先级（建议：面板配置 > custom_rates > 内置默认），或
   - 继续保证该文件不存在，并在面板/文档里写明"不要手动创建它"。
2. `/api/admin/gacha/config` 已有的 GET 接口可直接作为 P0 面板的数据源骨架（返回结构简单，扩字段成本低）。
3. Shittim 工作目录 = `/www/wwwroot/ba_srv`；`gacha_config.json` 却在 `/www/wwwroot/`（**上一级**），
   新配置文件若放 Shittim 目录，注意别和这个历史路径混淆。

---
**本次未 restart、未改配置、未部署。备份与快照均已完成。**
