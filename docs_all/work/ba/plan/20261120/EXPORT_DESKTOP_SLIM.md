# 桌面交付目录精简 · 20261120

- 执行时间：2026-11-20 23:5x（Asia/Shanghai）
- 操作范围：**只**操作 `C:\Users\su\Desktop\BA_交付_20261120\`（桌面副本）
- 源目录 `C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\`：**零写入 / 零删除 / 零改名**（本次只创建了本报告文件）
- 口径变更：上游源码不带，交付目录只留"我们自己写的东西"的单个 zip

---

## 1. 结果

桌面交付目录从 **7 项（2 目录 + 5 文件）** 变成 **3 个文件、0 个目录、合计 4,298,954 B**：

```
C:\Users\su\Desktop\BA_交付_20261120\
├─ BA_自研补丁_20261120.zip   4,197,452 B   sha256 27da7cb5…302c
├─ MANIFEST_ZIP.txt              39,269 B   sha256 5488d390…615d
└─ README.md                     62,233 B   sha256 cfde7515…c90a4
```

---

## 2. 删除明细（先数后删，数字均为实测）

| 对象（绝对路径） | 类型 | 文件数 | 字节 |
|---|---|---:|---:|
| `C:\Users\su\Desktop\BA_交付_20261120\服务端源码` | 目录 | 1,324 | 11,922,062（11.37 MiB，73 个子目录） |
| `C:\Users\su\Desktop\BA_交付_20261120\客户端相关` | 目录 | 324 | 6,609,709（6.30 MiB，19 个子目录） |
| `C:\Users\su\Desktop\BA_交付_20261120\MANIFEST_服务端源码.txt` | 文件 | 1 | 152,894 |
| `C:\Users\su\Desktop\BA_交付_20261120\MANIFEST_客户端相关.txt` | 文件 | 1 | 33,448 |
| **合计** | — | **1,650** | **18,718,113（17.85 MiB）** |

### 2.1 删除前的安全校验（已执行并打印）

对 4 个目标逐个打印后确认，才调用 `Remove-Item`：

```
C:\Users\su\Desktop\BA_交付_20261120\服务端源码
    under-delivery=True  reparse=False  type=DIR  files=1324  bytes=11922062
C:\Users\su\Desktop\BA_交付_20261120\客户端相关
    under-delivery=True  reparse=False  type=DIR  files=324   bytes=6609709
C:\Users\su\Desktop\BA_交付_20261120\MANIFEST_服务端源码.txt
    under-delivery=True  reparse=False  type=FILE files=1     bytes=152894
C:\Users\su\Desktop\BA_交付_20261120\MANIFEST_客户端相关.txt
    under-delivery=True  reparse=False  type=FILE files=1     bytes=33448
```

- `under-delivery=True`：`FullName` 严格以 `C:\Users\su\Desktop\BA_交付_20261120\` 开头。
- `reparse=False`：两个目录都不是 junction / symlink；整个交付目录树内 reparse point 计数 = **0**，不存在"删副本删到源目录"的风险。
- 实际删除命令只用 `Remove-Item -LiteralPath <写死的绝对路径> -Recurse -Force`。
- 删除后复核：`Test-Path` 四个目标全部 `False`。

---

## 3. zip 改名（未重打包）

| 项 | 值 |
|---|---|
| 原名 | `我们写的补丁与成品.zip` |
| 新名 | `BA_自研补丁_20261120.zip` |
| 大小 | 4,197,452 B（前后一致） |
| 改名**前** sha256 | `27da7cb51d077c62fa07ac21e14dbd3dfbe853cb55ee1c12746fe5e53f8a302c` |
| 改名**后** sha256 | `27da7cb51d077c62fa07ac21e14dbd3dfbe853cb55ee1c12746fe5e53f8a302c` |
| 一致性 | ✅ **完全相同**（`Rename-Item` 只改 Dirent 名字） |
| 条目数（中央目录） | 362 = 361 文件 + 根 `MANIFEST.txt` |
| 解压后合计 | 13,763,909 B = 13,724,640（361 文件）+ 39,269（`MANIFEST.txt`） |
| 压缩数据流合计 | 4,143,998 B |

---

## 4. 交付目录最终清单（`Get-ChildItem -Recurse -Force` 实际输出）

```
FILE        4197452 BA_自研补丁_20261120.zip
FILE          39269 MANIFEST_ZIP.txt
FILE          62233 README.md

FILE COUNT: 3   DIR COUNT: 0   TOTAL BYTES: 4298954
```

| 文件 | 字节 | sha256 |
|---|---:|---|
| `BA_自研补丁_20261120.zip` | 4,197,452 | `27da7cb51d077c62fa07ac21e14dbd3dfbe853cb55ee1c12746fe5e53f8a302c` |
| `MANIFEST_ZIP.txt` | 39,269 | `5488d3907c6c7c7b973fd23e3dcbac4cdbe4bbf9a06c08593c8e196bcd1a615d` |
| `README.md`（本次重写） | 62,233 | `cfde75150c2c961bd771f004e706a6b7b57c690f3ec47e8adadacf20f07c90a4` |

---

## 5. 新 README 的目录结构树（zip 内部，共 362 条目 / 13,763,909 B）

```
BA_自研补丁_20261120.zip/   362 个文件 / 13,763,909 B（4,197,452 B 压缩包）
├─ bridge/                     16 个文件       628,359 B  桥 / 90004 补丁与校验脚本、systemd 说明
├─ client/                    308 个文件     4,334,362 B  客户端补丁：smali、资源、构建脚本
│  ├─ apk_patch/              134 个文件     1,233,390 B  APK 补丁工作区（基线清单、成品脚本）
│  │  ├─ patched/               4 个文件       115,419 B  直接上的 smali / layout 补丁
│  │  ├─ scripts/              45 个文件       101,433 B  apktool 解包/重打/自检脚本
│  │  ├─ v2v3/                 29 个文件       266,021 B  v2/v3 签名包裹试验
│  │  ├─ v4/                   36 个文件       392,074 B  登录页布局试验 v4
│  │  │  └─ smali_probe/       12 个文件        85,984 B  v4 smali 探针
│  │  └─ v5/                   18 个文件       319,256 B  登录页布局 v5（res_Q9_v5）
│  └─ noroot/                 174 个文件     3,100,972 B  免 root 构建（含签名材料，注意保管）
│     ├─ _extract/              3 个文件         9,479 B  APK 抽取样本
│     ├─ _extract_cn/           5 个文件        16,437 B  中文资源抽取
│     ├─ _kit/                  7 个文件        37,682 B  探针工具包
│     │  └─ BA_probe_kit_v1/    7 个文件        37,682 B  探针包 v1
│     │     ├─ pc/              3 个文件        18,813 B  探针包 v1 · PC 端
│     │     └─ phone/           3 个文件        10,162 B  探针包 v1 · 手机端
│     ├─ _probe/                4 个文件        16,936 B  探针输出
│     └─ diff24000/            25 个文件       197,542 B  diff 24000 比对结果
├─ docs/                       18 个文件       364,747 B  自研文档（根因/部署/回滚/交接）
├─ panel/                       6 个文件       125,888 B  管理面板 PHP
│  ├─ inc/                      3 个文件        61,783 B  面板 include
│  ├─ pages/                    2 个文件        48,298 B  面板页面
│  └─ variant_p0rates/          1 个文件        15,807 B  p0rates 变体（仅对照）
│     └─ pages/                 1 个文件        15,807 B  p0rates 变体页面
└─ server/                     13 个文件     8,271,284 B  已编译服务端 DLL（线上同款）
   ├─ Data/                     3 个文件        41,531 B  抽卡配置（529 横幅 / 4 组概率）
   ├─ Resources/                7 个文件        93,832 B  7 份客户端 id 白名单
   └─ Services/                 1 个文件        15,601 B  ClientItemFilter.cs 源码单件
MANIFEST.txt                    1 个文件        39,269 B  逐文件清单
```

对账：5 个顶层目录 16+308+18+6+13 = **361** 文件；628,359+4,334,362+364,747+125,888+8,271,284 = **13,724,640 B**，再加 `MANIFEST.txt` 39,269 B = 13,763,909 B，与 zip 中央目录一致。

---

## 6. 新 README 章节结构

| 节 | 内容 |
|---|---|
| 0 | 目录现状（只剩 zip + MANIFEST_ZIP.txt + README.md） |
| 1 | zip 路径 / 大小 / sha256 / 条目数 / 解压后大小；1.1 包内关键产物速查（12 项） |
| 2 | 内部结构树（上面第 5 节那棵，含每目录文件数与字节） |
| 3 | 清单表：24 个目录分组，**361 行**逐文件 `相对路径 / 字节 / sha256` 全列 |
| 4 | 包里没有的东西及原因（上游源码、10.6 GB 成品 APK、`_build_*`、`decode\`、`libil2cpp.so` 等 12 项） |
| 5 | 怎么用：解压 / DLL 放哪 / `systemctl restart ba-bridge` / 面板文件放哪 / 补丁脚本怎么跑 |
| 6 | 已知缺口：置顶告警（桥 ≠ 线上 `15758f0e…`）+ 原 README 4.4 的 9 条表原样保留 |
| 7 | 本次精简记录（删除/改名/未动，可核对） |
| 8 | 自检（hash 一致、条目数对账、逐文件复核方式、源目录零写入） |

---

## 7. 已知缺口（原 README 4.4 三条"未找到/不一致"，原样保留）

> ⚠️ **zip 里的桥不是线上正在跑的那一份**：线上 `/www/wwwroot/bapatch/tools/account_auth_probe.py`（2026-11-20）sha256 = `15758f0e…`（md5 `891178d6…`）；包里两份本地副本 `bridge/account_auth_probe.py`（167,430 B，`16d4efcb…`）与 `bridge/account_auth_probe.py.v222486`（228,722 B，`6756a5de…`）**都与线上不是字节相同**。覆盖前必须 `sha256sum`/`md5sum` 对照。

1. `work\ba\server\deploy\_ba_state\` 目录 —— **未找到**（全树 0 命中；它是线上路径，本地对应物 `_p90004\90004_ops.json` 已收进 `bridge/90004_ops.json`）
2. 线上桥脚本的字节级副本 —— **未找到**（两份本地副本都不等于 `15758f0e…`）
3. `inc\helpers.php` 的独立改动说明 / diff —— **未找到**（helpers.php 与 p0rates 版逐字节相同，改动集中在 gacha.php / gacha_rates.php / gm_lobby.php / items.php）

---

## 8. 遗留与注意事项

| 项 | 说明 |
|---|---|
| `MANIFEST_ZIP.txt` 首行 | 仍写"`# MANIFEST - 我们写的补丁与成品.zip`"。它与 zip 内 `MANIFEST.txt` 是**同一份文本**（已实测逐字节相同：两边 sha256 均为 `5488d390…615d`），本次按"只改名 + 改 README、不重打包"的要求**未改写**，避免与 zip 内清单产生差异 |
| 服务端源码已不在包内 | 新机器上无法 `dotnet build` 重建 DLL，只能部署 `server/*.dll`；要改源码回 `work\ba\` |
| 客户端成品 APK | 依旧不带（10.6 GB），用 `client/apk_patch/scripts/` + `client/noroot/build_noroot_apk.py` 自行重打 |
| zip 内部内容 | 本次**没有**重新解压/重打包；后续如需更新包内容，另起一轮再做 |

---

## 9. 复核命令

```powershell
$d = 'C:\Users\su\Desktop\BA_交付_20261120'
Get-ChildItem -LiteralPath $d -Recurse -Force            # 应只有 3 个文件、0 个目录
(Get-FileHash -LiteralPath "$d\BA_自研补丁_20261120.zip" -Algorithm SHA256).Hash
# 期望 27DA7CB51D077C62FA07AC21E14DBD3DFBE853CB55EE1C12746FE5E53F8A302C
```
