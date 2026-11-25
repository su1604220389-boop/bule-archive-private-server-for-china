# 桌面交付包 EXPORT_DESKTOP（2026-11-20）

- 执行时间：2026-11-20 23:45 起（Asia/Shanghai）
- 动作：**只读复制 + 一次 zip 打包**。没有修改、删除、重命名任何源文件；所有新文件都建在桌面。
- 交付目录：`C:\Users\su\Desktop\BA_交付_20261120\`

## 一句话结论

交付目录已建好，共 **1,653 个文件 / 22,972,548 B（21.91 MiB）**；服务端源码 11.37 MiB、客户端相关 6.30 MiB、
`我们写的补丁与成品.zip` 4.00 MiB（sha256 `27da7cb51d077c62fa07ac21e14dbd3dfbe853cb55ee1c12746fe5e53f8a302c`）。

## 1. 交付目录结构树

```
C:\Users\su\Desktop\BA_交付_20261120\
├─ README.md                        17,714 B   三块清单 + 未包含原因 + 怎么用
├─ MANIFEST_服务端源码.txt         152,894 B   1,324 行（路径/字节/sha256）
├─ MANIFEST_客户端相关.txt          33,448 B     324 行
├─ MANIFEST_ZIP.txt                 39,269 B     361 行（= zip 内 MANIFEST.txt 的包外副本）
├─ 我们写的补丁与成品.zip         4,197,452 B   sha256 27da7cb5…，362 条
├─ 服务端源码\                     11.37 MiB / 1,324 文件   （未压缩，原样结构）
│  ├─ global.json  Directory.Build.props          ← 补进来的构建前提（源目录根上就有）
│  ├─ Shittim-Server\                            2.71 MiB / 283 文件
│  │  ├─ CLI\ Commands\ config\ Configuration\ Controllers\ Core\ Data\
│  │  ├─ Extensions\ GameClient\ GameMasters\ Managers\ Models\ Properties\
│  │  └─ Resources\(7 份 id 白名单)  Services\  Utils\  *.cs / *.csproj / appsettings*.json
│  └─ Schale\                                    8.66 MiB / 1,039 文件
│     ├─ Crypto\ Data\ Excel\ Extensions\ FlatData\(888) MappingProfiles\ MX\
│     └─ BlueArchive.fbs  Schale.csproj
├─ 客户端相关\                     6.30 MiB / 324 文件     （未压缩，原样结构）
│  ├─ apk_patch\                                 1.18 MiB / 134
│  │  ├─ scripts\ (43 个 .py/.sh + 2 个 .log)
│  │  ├─ patched\ (3 个 .smali + extend_edit_login_layout.xml)
│  │  ├─ v2v3\ (29)  v4\ (36, 含 smali_probe\)  v5\ (18)
│  │  └─ BASELINE_MANIFEST.json  STEP1_REPORT.md
│  ├─ noroot\                                    2.96 MiB / 174
│  │  ├─ build_noroot_apk.py、NOROOT_*.md、GMCONFIG_*.md、SIGNER_FIXES.md…
│  │  ├─ ba_private.keystore / .key.pem / .cert.pem   ← 签名材料
│  │  ├─ diff24000\ (25)  _kit\ (7)  _probe\ (4)  _extract\ (3)  _extract_cn\ (5)
│  └─ audit_ba_apk\                              2.17 MiB / 16
│     ├─ zip_listing.txt (2.21 MB)
│     └─ out\ (kw.txt, kw-hits.tsv, name-families.txt, dyn-*.so.txt ×9, strings\ ×3)
└─ 我们写的补丁与成品.zip          （唯一压缩件）
   ├─ MANIFEST.txt                 361 个文件的 path/bytes/sha256
   ├─ bridge\   16 个
   ├─ server\   13 个（2 DLL + 3 Data + 7 Resources + ClientItemFilter.cs）
   ├─ panel\     6 个（5 个面板文件 + 1 个对照变体）
   ├─ client\  308 个（apk_patch 134 + noroot 174）
   └─ docs\     18 个
```

## 2. 每块大小

| 区块 | 文件数 | 字节 | 人类可读 |
|---|---:|---:|---|
| `服务端源码\` | 1,324 | 11,922,062 | 11.37 MiB |
| `客户端相关\` | 324 | 6,609,709 | 6.30 MiB |
| `我们写的补丁与成品.zip` | 362 条 | 4,197,452 | 4.00 MiB |
| 清单 3 份 + README | 4 | 243,325 | 0.23 MiB |
| **合计** | **1,653** | **22,972,548** | **21.91 MiB** |

源侧参照（未动）：`srv_src\Shittim-Server` 193,186,483 B、`srv_src\Schale` 53,598,059 B →
去掉 `bin`/`obj` 后剩 11.37 MiB，**构建产物占了 96%**。

## 3. zip 的 sha256

```
文件：C:\Users\su\Desktop\BA_交付_20261120\我们写的补丁与成品.zip
大小：4,197,452 B
sha256：27da7cb51d077c62fa07ac21e14dbd3dfbe853cb55ee1c12746fe5e53f8a302c
条目：362（361 文件 + MANIFEST.txt）
```

- 打包工具：`System.IO.Compression.ZipArchive`（逐条 `CreateEntry`，路径统一 forward slash）。
  **没有用 `Compress-Archive`**：PS 5.1 的 `Compress-Archive` 会写出反斜杠条目（`bridge\xxx.py`），在 Linux 解压会变成一个怪文件名。
- 打包前先把文件复制到桌面临时 staging（`BA_交付_20261120\_staging_zip`），打完即删，源目录只被读。

## 4. 排除清单（含路径与大小）

| # | 路径 | 大小 | 排除理由 |
|---|---|---:|---|
| 1 | `work\ba\apk_patch\out\`（5 个 APK 成品） | 10,660,372,241 B（9.93 GiB） | 2 GB 级成品，可重打 |
| 2 | `work\ba\server\deploy\_noroot\`（26 文件） | 4,262,928,771 B（3.97 GiB） | APK/日志搬运区，不在本次范围 |
| 3 | `work\ba\apk_patch\backup\`（1 个 APK） | 2,127,971,177 B（2.03 GB） | 2 GB 级成品 |
| 4 | `work\ba\noroot\BA_noroot_prod_20261118_v1.apk` | 2,127,971,177 B | 2 GB 级成品 |
| 5 | `work\ba\noroot\BA_noroot_v1.apk` | 2,127,962,985 B | 2 GB 级成品 |
| 6 | `work\ba\srv_src\_build_*\`（20 个目录） | 1,379,477,381 B | 构建产物 |
| 7 | `work\ba\audit\ba-apk\lib\`（24 个 .so） | 317,375,216 B | 大二进制 |
| 8 | `work\ba\noroot\_tmp\libil2cpp.so` | 270,927,056 B | 大二进制 |
| 9 | `work\ba\apk_patch\decode\`（17,710 文件） | 167,598,935 B | `decode\` > 100 MiB 规则 |
| 10 | `work\ba\noroot\freeze_20261118\logcat_verbose.txt` | 52,591,807 B | 原生日志 |
| 11 | `work\ba\noroot\_extract\gm-global-metadata.dat` | 33,351,780 B | 单文件 > 20 MiB |
| 12 | `work\ba\noroot\_tmp\libunity.so` | 20,950,552 B | 大二进制 |
| 13 | `work\ba\apk_patch\slim\slim.apk` | 15,828,657 B | APK |
| 14 | `srv_src\Shittim-Server\bin\` | 179,258,740 B | 编译输出（367 文件） |
| 15 | `srv_src\Schale\obj\` | 28,755,073 B | 中间产物 |
| 16 | `srv_src\Schale\bin\` | 15,763,246 B | 编译输出 |
| 17 | `srv_src\Shittim-Server\obj\` | 11,085,974 B | 中间产物 |
| 18 | `apk_patch\v2v3\classes_patched.dex` + `smali_cmp\classes_orig.dex` | 9,327,708 B ×2 | dex 产物 |
| 19 | `apk_patch\v2v3\wrap_new.apk` / `wrap_orig.apk` | 2,255 / 1,980 B | 试验 APK |
| 20 | `audit\ba-apk\jadx\`、`classes.dex`、`classes2.dex`、`resources.arsc`、`slim.apk` | 12.4 MiB + 8.9 + 9.7 + 1.1 + 7.6 MiB | 反编译/解包产物 |
| 21 | `srv_src\build_plain.log`、`shittim_src_20261117-024413.tgz` | 281,036 / 1,691,118 B | 构建日志 / 源码快照 |
| 22 | `plan\20261119` 其余 36 份 md | — | 只收 16 份关键件 |
| 23 | `.git` | **0 个（全树未发现）** | 无需排除 |

规则性排除（未逐条列）：所有 `*.pdb`、`*.deps.json`、`TestResults\`、`.vs\`、`__pycache__\`、`*.bak*`/`*.orig`（客户端脚本的历史备份）。

## 5. 未找到项

| 目标 | 结论 |
|---|---|
| `work\ba\server\deploy\_ba_state\`（本地目录） | **未找到**。全 `work\ba` 树递归 0 命中；它是线上路径 `/www/wwwroot/bapatch/_ba_state/`。本地对应物 `_p90004\90004_ops.json` 已作为 `bridge/90004_ops.json` 收进 zip（sha256 `938ae908…`，与 `D90004_DEPLOY.md` 记录一致） |
| 线上桥脚本（sha256 `15758f0e…`）的字节级副本 | **未找到**。zip 内放了 `_p90004` 的两份（167,430 B / 228,722 B），都与线上不同；已在 README 5.3 写明选型警告 |
| `inc\helpers.php` 的独立改动说明/diff | **未找到**。`gm_lobby` 与 `p0rates` 两份 helpers.php 逐字节相同（sha256 `0bd35a74…`），实际改动在 gacha.php / gacha_rates.php / gm_lobby.php / items.php |

## 6. 关键一致性核对

| 检查 | 结果 |
|---|---|
| `Shittim-Server.dll` sha256 vs 线上 `c013f442…` | ✅ `c013f4427ad01d44c00cc63af3de817b800638fcd8ec0ee55de41126aed106aa` |
| `90004_ops.json` sha256 vs `D90004_DEPLOY.md` | ✅ `938ae90855b5fa5fa11342854f2e0f28e7130b466c303621151685efc06107fb` |
| `patch_90004.py` sha256 vs `D90004_DEPLOY.md`（`c94bae46…`） | ✅ `c94bae46d6d052945b16446e4f5a35a9cdaf8e3dae896200ece6be5dca4589cf` |
| `GachaRecruitBanners.cn.json` 529 条 | ✅ 40,739 B，`"Id"` 计数 529 |
| zip 解压回归：按 `MANIFEST_ZIP.txt` 逐条重算 sha256 | ✅ 361/361 通过，0 不符 |
| 源目录是否被动过 | ✅ 只读（`robocopy` / `Copy-Item` 读源；压缩在 staging 上做） |

## 7. 复现命令（供复核）

```powershell
# 校验 zip 本体
Get-FileHash 'C:\Users\su\Desktop\BA_交付_20261120\我们写的补丁与成品.zip' -Algorithm SHA256

# 逐条校验 zip 内容
$tmp="$env:TEMP\ba_zip_check"; Remove-Item $tmp -Recurse -Force -EA 0
Expand-Archive 'C:\Users\su\Desktop\BA_交付_20261120\我们写的补丁与成品.zip' $tmp
Get-Content (Join-Path ($tmp,'MANIFEST.txt')) | Where-Object {$_ -notmatch '^#' -and $_.Trim()} | ForEach-Object {
  $p,$b,$h = $_ -split "`t"
  $f = Join-Path $tmp ($p -replace '/','\')
  if ((Get-FileHash $f -Algorithm SHA256).Hash.ToLower() -ne $h) { "BAD $p" }
}
```
