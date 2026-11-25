# EXPORT_ZIP_BRIDGE_SWAP — 桌面交付包内桥替换为线上真身

- 日期：2026-11-20 23:5x（Asia/Shanghai）
- 范围：**只改桌面交付 zip 内部**。服务器未 ssh / 未 scp / 未重启；`work\ba\` 源目录只读拉取，未写入任何文件。
- 结论：**替换并重打包完成，逐条校验 362/362 100% 通过。**

---

## 1. 线上真身核对（拉取后、使用前）

来源：`C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_live\LIVE_20261120\account_auth_probe.py`
线上路径：`/www/wwwroot/bapatch/tools/account_auth_probe.py`
拉取时间：2026-11-20 23:50（mtime `2026-11-20 23:50:54`）

| 项 | 预期 | 实测 | 结论 |
|---|---|---:|---|
| 字节 | 228,775 | 228,775 | ✅ |
| sha256 | `15758f0ea007dcfba4e46fc4620dd183329381c194f00878abd6acc21cd2ee01` | 同左 | ✅ |
| md5 | `891178d6ba9647d27a1d8b2f5d7c2d64` | 同左 | ✅ |

三项全部对上后才继续；任何一项不符即停止回报（未触发）。
源文件在本操作结束后复核仍为 228,775 B / `15758f0e…`，**未被改动**。

---

## 2. 新旧桥 sha256 对照

| 位置 | 文件 | 字节 | md5 | sha256 |
|---|---|---:|---|---|
| 包内（替换前，主副本） | `bridge/account_auth_probe.py` | 167,430 | — | `16d4efcb2cb0b03c380942c66c6a0887b270596ce04741b0dd1895a2c5108688` |
| 包内（替换前，第二副本） | `bridge/account_auth_probe.py.v222486` | 228,722 | — | `6756a5defb8e1c33b43d03d2fc2d24972955dbf6464695be0a157f2ab8828e40` |
| **包内（替换后，主位）** | `bridge/account_auth_probe.py` | **228,775** | `891178d6ba9647d27a1d8b2f5d7c2d64` | **`15758f0ea007dcfba4e46fc4620dd183329381c194f00878abd6acc21cd2ee01`** |
| 线上真身（同一份） | `account_auth_probe.py` | 228,775 | `891178d6ba9647d27a1d8b2f5d7c2d64` | `15758f0ea007dcfba4e46fc4620dd183329381c194f00878abd6acc21cd2ee01` |

包内主位与线上真身 **字节相同**（sha256 一致）。

---

## 3. `bridge/_history/` 文件清单（旧副本保留，未删除）

两份旧副本内容一字节未改，仅移动 + 改名标明版本与源 hash。

| 新路径（zip 内） | 原路径 | 字节 | sha256 |
|---|---|---:|---|
| `bridge/_history/account_auth_probe.p90004-16d4efcb.py` | `bridge/account_auth_probe.py` | 167,430 | `16d4efcb2cb0b03c380942c66c6a0887b270596ce04741b0dd1895a2c5108688` |
| `bridge/_history/account_auth_probe.v222486-6756a5de.py` | `bridge/account_auth_probe.py.v222486` | 228,722 | `6756a5defb8e1c33b43d03d2fc2d24972955dbf6464695be0a157f2ab8828e40` |

> 校验：移动前后两份的 sha256 与原文完全一致（`16d4efcb…` / `6756a5de…`），证明只是改名改路径，未触碰内容。

包内 `bridge/` 目录：**16 → 17 个文件**（替换 1 + 新增 1 个主位副本，旧两份保留），字节 628,359 → **857,134 B**。

---

## 4. 清单 MANIFEST.txt 更新

- 全量重算：按磁盘实际文件逐个算字节 + sha256，**362 行**全部重写（不是只改几行）。
- 格式保持：UTF-8（无 BOM）、CRLF、`相对路径<TAB>字节<TAB>sha256`；路径一律正斜杠。
- 排序：沿用原清单的区域性 `Sort-Object` 顺序（已实测该比较器能逐行复现原始 361 行顺序）。
- 头部新增 6 行变更记录注释，# 开头，不影响解析。
- 尾部合计行：`# 合计: 362 个文件, 13953415 字节`。
- 清单自身不计入清单（与原来一致）。

变更集（新旧清单逐条比对结果）：

| 类别 | 数量 | 明细 |
|---|---:|---|
| 未变（路径+字节+sha256 全同） | 359 | — |
| 原地替换 | 1 | `bridge/account_auth_probe.py` |
| 路径消失（被改名移走） | 1 | `bridge/account_auth_probe.py.v222486` |
| 新增路径 | 2 | `bridge/_history/account_auth_probe.p90004-16d4efcb.py`、`bridge/_history/account_auth_probe.v222486-6756a5de.py` |

字节账：13,724,640（旧 361 文件）+ 228,775（真身净增）= **13,953,415**；+ `MANIFEST.txt` 40,008 = **13,993,423**。

---

## 5. 重打包前后 zip 对照

| 项 | 重打包前 | 重打包后 |
|---|---:|---:|
| 文件 | `BA_自研补丁_20261120.zip` | 同左（覆盖桌面旧 zip） |
| 大小 | 4,197,452 B（4.00 MiB） | **4,262,879 B（4.07 MiB）** |
| sha256 | `27da7cb51d077c62fa07ac21e14dbd3dfbe853cb55ee1c12746fe5e53f8a302c` | **`5a25a07d723f322abc680babace75a45a44d6675a3c13660cc01e765406de08a`** |
| 中央目录条目数 | 362（361 文件 + `MANIFEST.txt`） | **363（362 文件 + `MANIFEST.txt`）** |
| 解压后合计 | 13,763,909 B | **13,993,423 B** |
| 压缩数据流合计 | 4,143,998 B | 4,209,207 B |

打包实现：.NET `System.IO.Compression.ZipArchive`（`CompressionLevel.Optimal`），条目名显式使用正斜杠。
**未使用 `Compress-Archive`**（PS 5.1 会写反斜杠条目）。实测结果：反斜杠条目 **0**、重复条目 **0**、绝对路径/盘符条目 **0**。

---

## 6. 逐条校验结果（100% 通过）

校验方法：把**桌面最终 zip** 解压到一个全新空目录，按包内 `MANIFEST.txt` 的 362 行逐条比对「字节 + sha256」。

| 检查项 | 结果 |
|---|---|
| MANIFEST 逐条比对（字节 + sha256） | **362 / 362 通过，0 失败** |
| 磁盘上存在但清单未列的文件 | 0 |
| 清单列了但解压目录缺失的文件 | 0 |
| `bridge/account_auth_probe.py` 包内 sha256 = `15758f0e…` | ✅ |
| `MANIFEST_ZIP.txt` 与包内 `MANIFEST.txt` 逐字节相同 | ✅ |
| 反向：README.md 表格 375 行对 MANIFEST 复核 | 375 / 375 通过；362 个条目在 README 中均有出现 |

> 校验复现命令（PowerShell 5.1 必须显式 `-Encoding UTF8`，否则默认按 ANSI 解码中文清单会读出乱码）：
> ```powershell
> Get-Content .\MANIFEST.txt -Encoding UTF8 | ForEach-Object {
>   $p = $_ -split "`t"; if ($p.Count -eq 3) {
>     $f = Get-Item -LiteralPath ($p[0] -replace '/','\')
>     $h = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower()
>     if ($f.Length -ne [int64]$p[1] -or $h -ne $p[2]) { "FAIL $($p[0])" }
>   }
> }
> ```

---

## 7. 桌面交付目录最终状态

`C:\Users\su\Desktop\BA_交付_20261120\`

| 文件 | 字节 | sha256 |
|---|---:|---|
| `BA_自研补丁_20261120.zip` | 4,262,879 | `5a25a07d723f322abc680babace75a45a44d6675a3c13660cc01e765406de08a` |
| `MANIFEST_ZIP.txt` | 40,008 | `82d87aa147e64b0a22a5a264b7a3b19c3089d78970a07ce69124ad4ece7e6ce7` |
| `README.md` | 65,451 | `6937594cd8a691b4062f4d999e74d123af45414b41e7bfd3225a699f0b73dbbc` |

README 改动要点：
1. §0 之前新增显著章节「✅ 包内桥已替换为线上真身（2026-11-20 23:52）」，含 228,775 B / `15758f0e…` / md5 / 来源 `/www/wwwroot/bapatch/tools/account_auth_probe.py` / 拉取时间 2026-11-20 23:50 / 旧副本去向。
2. §6「线上桥脚本的字节级副本 = 未找到」整条改写为 **已解决**，并由 ⚠️ 警示降级为 ✅ 已完成说明。
3. §5.3「覆盖前先比 sha256：zip 里的桥不是线上那份」改为「已是线上真身，可直接覆盖；`_history/` 仅留存」。
4. §1 / §2 / §3 / §7 / §8 中所有受重打包影响的数字（大小、sha256、条目数、解压合计、目录文件数）逐项更新，并把两个旧桥行拆成「真身 + 2 个 `_history` 行」。

---

## 8. 红线自检

| 约束 | 结果 |
|---|---|
| 不 ssh / 不 scp / 不重启服务器 | ✅ 全程未联网、未起任何远程会话 |
| 不改 `work\ba\` 下任何文件 | ✅ 只读 `ReadAllBytes` / `Get-FileHash`；本次报告是本任务指定的新交付件，除此之外 `work\ba\` 零写入 |
| 只改桌面 zip / README.md / MANIFEST_ZIP.txt | ✅ 该目录内只写这 3 个文件；无新增/删除其它文件 |
| 只在自己建的临时目录工作 | ✅ `C:\Users\su\Desktop\_tmp_delivery\`（用完已删） |
| 不改任何代码逻辑 | ✅ 桥文件按线上真身原样落盘，未做任何编辑；旧副本只改名未改内容 |
| 旧的两个副本不删 | ✅ 两份均在 `bridge/_history/`，sha256 与原文一致 |

---

## 9. 遗留提醒

- 桌面 `README.md` 在我作业期间（23:52:31）被另一个并行任务整体重写过（把交付目录精简为只剩 zip + 2 份清单/说明）。我的写入基于**那次重写后的版本**做定点替换，替换脚本 27 个块全部「恰好命中 1 次」才落盘，因此没有覆盖对方的精简改动。若该并行任务之后又写 README，需重新确认桥替换那段是否仍在。
- `bridge/_history/` 里两份旧副本仅供追溯，**部署时不要上传**。
