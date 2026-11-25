# 线上真实文件拉取（LIVE_20261120）

- 时间：2026-11-20 23:50–23:51（Asia/Shanghai）｜ 执行：srv-ops
- 性质：**只读拉取**（服务器侧只执行 `ls/stat/sha256sum/md5sum/cat`；未 mv/chmod/sed/cp 覆盖任何东西、未重启服务、未部署）
- 本地目标：`work\ba\srv_live\LIVE_20261120\`

## 一句话结论

**线上桥脚本已拉下，sha256 = `15758f0ea007dcfba4e46fc4620dd183329381c194f00878abd6acc21cd2ee01`（228,775 B）**，与服务器一致；
5 个面板文件 sha256 **全部与预期逐字一致**；`_ba_state/` 只有 1 个文件（`90004_ops.json`，sha256 匹配）；
Shittim DLL = `c013f442…` 复核通过。

---

## 1. 桥脚本（最重要）

| 项 | 服务器 | 本地 | 一致 |
|---|---|---|---|
| 路径 | `/www/wwwroot/bapatch/tools/account_auth_probe.py` | `work\ba\srv_live\LIVE_20261120\account_auth_probe.py` | — |
| 大小 | 228,775 B | 228,775 B | ✅ |
| **sha256** | **`15758f0ea007dcfba4e46fc4620dd183329381c194f00878abd6acc21cd2ee01`** | **同值** | ✅ |
| md5 | `891178d6ba9647d27a1d8b2f5d7c2d64` | 同值 | ✅ |
| 属主/时间 | `root:root ｜ mtime 2026-11-19 02:12:30` | — | — |

**三个副本的 sha256 对照（佐证必须拿线上真身）**
| 来源 | 大小 | sha256 | 说明 |
|---|---|---|---|
| 交付包副本 A | 167,430 B | `16d4efcb…` | 旧，不同 |
| 交付包副本 B | 228,722 B | `6756a5de…` | 大小接近但仍是另一版本 |
| **线上真身（本次拉取）** | **228,775 B** | **`15758f0e…`** | **以这份为准** |

> 原始字节拉取，未做任何转换（Windows 上重算 sha256 与服务器逐字相同即证明未被改动；CRLF 转换会立刻改变哈希）。

## 2. `_ba_state/` 全目录（只有 1 个文件）

```
服务器：ls -la /www/wwwroot/bapatch/_ba_state/
total 20
drwxr-xr-x  2 root root  4096 Nov 19 02:12 .
drwxr-xr-x 15 www  www   4096 Nov 19 02:12 ..
-rw-r--r--  1 root root 10883 Nov 19 02:12 90004_ops.json
```
| 文件 | 大小 | sha256 | 预期 | 一致 |
|---|---|---|---|---|
| `90004_ops.json` | 10,883 B | `938ae90855b5fa5fa11342854f2e0f28e7130b466c303621151685efc06107fb` | `938ae908…` | ✅ |

本地路径：`work\ba\srv_live\LIVE_20261120\_ba_state\90004_ops.json`

## 3. `ba-bridge.service`（原文）

| 项 | 值 |
|---|---|
| 服务器路径 | `/etc/systemd/system/ba-bridge.service` |
| 大小 | 479 B |
| sha256 | `410e27a5d288318f55a892707b92b96d3dd9d22648ae1b2f3b2efab1e45dc287` |
| 本地路径 | `work\ba\srv_live\LIVE_20261120\systemd\ba-bridge.service`（sha256 同值 ✅） |

```ini
[Unit]
Description=BA auth bridge (account_auth_probe) on 9097
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/www/wwwroot/bapatch/tools
UMask=007
ExecStart=/usr/bin/python3 /www/wwwroot/bapatch/tools/account_auth_probe.py
Restart=always
RestartSec=5
StandardOutput=append:/www/wwwroot/bapatch/logs/bridge_stdout.log
StandardError=append:/www/wwwroot/bapatch/logs/bridge_stdout.log

[Install]
WantedBy=multi-user.target
```

## 4. 面板 5 个关键文件（仅核对，不用于覆盖）

| 文件 | 大小 | sha256 | 预期 | 一致 |
|---|---|---|---|---|
| `inc/helpers.php` | 29,131 B | `0bd35a74fed7c932bf232f1fb0bf49efd738448e6bd122c1c9830539a4d4a371` | `0bd35a74…` | ✅ |
| `inc/gacha.php` | 17,073 B | `1152ff4c5f16372f7cec78a3b458d45dd0e4ed2781b4f396d6634d2f1e3a4e94` | `1152ff4c…` | ✅ |
| `pages/gacha_rates.php` | 24,050 B | `105f151cd539322f26ffaa54d32a250c084b82d99536516249f3318d36e1bfdd` | `105f151c…` | ✅ |
| `inc/gm_lobby.php` | 15,579 B | `7623fe9889eac4c26e1d8b45eaad7a21049f45c158288f7247b06cbdb74ec268` | `7623fe98…` | ✅ |
| `pages/items.php` | 24,248 B | `25f7e2b3d29fec83fcc5abf57b121c2c733e491dd958d712f9693f4767dc0c26` | `25f7e2b3…` | ✅ |

本地路径（保留目录结构）：
```
work\ba\srv_live\LIVE_20261120\ba_cardadmin\inc\helpers.php
work\ba\srv_live\LIVE_20261120\ba_cardadmin\inc\gacha.php
work\ba\srv_live\LIVE_20261120\ba_cardadmin\inc\gm_lobby.php
work\ba\srv_live\LIVE_20261120\ba_cardadmin\pages\gacha_rates.php
work\ba\srv_live\LIVE_20261120\ba_cardadmin\pages\items.php
```

## 5. Shittim DLL 复核（只校验，未拉取）

```
服务器：-rw-r--r-- 1 root root 2,727,424 Nov 19 02:46 /www/wwwroot/ba_srv/Shittim-Server.dll
sha256 = c013f4427ad01d44c00cc63af3de817b800638fcd8ec0ee55de41126aed106aa   ← 与预期一致 ✅
```

## 6. 两侧逐项比对总表（本地重算 vs 服务器 sha256sum）

| # | 文件 | 大小 | 服务器 sha256 | 本地 sha256 | 一致 |
|---|---|---|---|---|---|
| 1 | account_auth_probe.py | 228,775 | `15758f0e…` | `15758f0e…` | ✅ |
| 2 | _ba_state/90004_ops.json | 10,883 | `938ae908…` | `938ae908…` | ✅ |
| 3 | systemd/ba-bridge.service | 479 | `410e27a5…` | `410e27a5…` | ✅ |
| 4 | ba_cardadmin/inc/helpers.php | 29,131 | `0bd35a74…` | `0bd35a74…` | ✅ |
| 5 | ba_cardadmin/inc/gacha.php | 17,073 | `1152ff4c…` | `1152ff4c…` | ✅ |
| 6 | ba_cardadmin/pages/gacha_rates.php | 24,050 | `105f151c…` | `105f151c…` | ✅ |
| 7 | ba_cardadmin/inc/gm_lobby.php | 15,579 | `7623fe98…` | `7623fe98…` | ✅ |
| 8 | ba_cardadmin/pages/items.php | 24,248 | `25f7e2b3…` | `25f7e2b3…` | ✅ |

**8/8 全部一致。**

本地清单文件：`work\ba\srv_live\LIVE_20261120\SHA256SUMS.txt`（含每项 sha256 + 字节数 + md5 + 相对路径）

## 7. 服务状态（只读确认，未动）

```
ba-bridge / ba-shittim / nginx / php-fpm-82 / mysqld  → 全部 active
```

## 8. 备注

- 桥脚本 md5 `891178d6…` 与 11-19 02:12 那次 D90004 部署后记录一致，未被改动（本次只读）。
- `_ba_state/` 里**只有** `90004_ops.json`；之前跑 90004 验证时桥写的其它落盘文件（`last_direct_envelope_plain.txt` 等）在 `/www/wwwroot/_ba_state/`（另一个目录），不在桥目录下 —— 如需要可另行拉取。
- 拉取全程未在服务器上做任何写操作；本地仅新增 `work\ba\srv_live\LIVE_20261120\` 下的文件。
