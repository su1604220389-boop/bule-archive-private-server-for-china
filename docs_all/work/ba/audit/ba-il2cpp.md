# BA 国服 IL2CPP 层取证（只读）

> WS=`/data/user/0/com.ai.assistance.operit/files/workspace/9dc0fd0c-7cad-4366-8d0b-bad7165d8587`
> 输入全部为现成产物，未复制/解包 base.apk，未联网、未安装、未启动游戏。作者：recon-il2cpp2（team）。
> 每条结论带命令与输出；取不到的写「未取到 / 未验证」，不编造。

## 一、`global-metadata.dat` 加密性：定论

文件：`$WS/audit/ba-work/x/assets/bin/Data/Managed/Metadata/global-metadata.dat`，38,426,024 B。

| 检查 | 命令 | 实测输出 |
|---|---|---|
| 前 8 字节 | `xxd -l 32` | `9443 7212 184b 9eec 6667 6666 a662 6566 …` |
| magic | 小端 u32 @0 | **0x12724394**（标准 `0xFAB11BAF`） |
| version | 小端 u32 @4 | **0xEC9E4B18**（合法值应为 0x18–0x1F） |
| 第 3 个 u32（标准布局=stringLiteralOffset） | u32 @8 | **0x66666766 = 1,717,986,150 > 文件 38 MB → 越界** |
| 标准 magic 全文件搜索 | `grep -aco $'\xaf\x1b\xb1\xfa'` | **0** |
| 1 KB 窗口熵 / 可打印率 | python 分块统计 | off=0 H=7.66 pr=0.39；4 096 H=7.80/0.37；65 536 H=7.87/0.39；**1 MB H=4.93/0.95**；19 MB H=3.96/0.28；36 MB H=4.83/0.73 |
| 分段形态 | 4 KB 块可打印率 >0.8 判定 | **0–258 048 B 全 BIN**；0x3F000 起出现 8 字节步进记录（`c7ccb8e4 b8a9aac7` → `b8aaaac7`…，即结构表形态，非随机密文） |
| 名字首现偏移 | `grep -abo` | `UnityEngine`@1,105,607；`mscorlib`@6,465,657；首个 ASCII 游程 @198,754（非名字，属结构化噪声） |

**定论**：不是整文件加密。实态是「**头部 + 前段（≈0–0x3F000，252 KB）结构区被自定义改写/加密**，其后名字表与字面量表保持明文并铺满整个 38 MB」。
- 依据 1：header 4 个连续 u32 全部非法（magic/version/offset 越界），且全文件 0 处标准 sanity。
- 依据 2：0–252 KB 高熵(7.8)、可打印率≈0.37，之后 1 MB 处直接升到 0.95（典型「结构表混沌 + 字符串区明文」）。
- 依据 3：0x3F000 处仍是 8 字节步进记录（计数器可见），说明该区不是流密码整体涂抹，而是自定义布局/混淆过的表。
- **可直接吃 Il2CppDumper：预计失败**（version 非法、stringLiteralOffset 越界），但**本轮未实跑**（本机有 mono 6.8.0.105，但无 Il2CppDumper 可执行文件，属推断）。
- 工程后果：静态 `strings` 足以判定「某类/方法名在此版本是否存在」；定位函数仍须运行时按名解析或运行时内存 dump。

**Il2CppDumper 要跑需补什么（按当前文件逐项）**
1. `magic` 还原为 `0xFAB11BAF`（现 `0x12724394`）；`version` 还原为 0x18–0x1F 之一（现 `0xEC9E4B18`，无任何已知 layout 对应）。
2. `stringLiteralOffset` 必须 < 文件长（现 `0x66666766`=1.72e9 ≫ 38.4 MB），`stringLiteralCount/stringOffset/stringCount/typeDefinitionsOffset&Count/metadataUsage` 等头部字段目前全部不可信，需按真实 layout 重填或解出。
3. 0–0x3F000（≈252 KB）结构区先还原：该区高熵(7.8)、可打印率0.37，且 0x3F000 处仍是 8 字节步进记录 → 不是整体流密码，是自定义/混淆表；Il2CppDumper 不做解密。
4. 注意 `libil2cpp.so` 的 section header 也被混淆（`.dynsym` 不在任何段映射、`sh_info=1`），dump 出来要按 `PT_DYNAMIC` 走，别用 readelf 的 section 视图。
5. **更省的替代**：运行时内存 dump（进程里 metadata 已解好、magic/layout 正常）或直接用 il2cpp API 反射拿 `MethodInfo*`，静态还原只服务「离线偏移表」这一条收益有限的路线。

## 二、7 个关键 il2cpp API 的存在性（grep -cx）

源：`$WS/audit/ba-apk/out/strings/libil2cpp.so.txt`（77,730 行，现成 strings 全量）。

```
命令：for a in <7 names>; do grep -cx $a strings/libil2cpp.so.txt; done
il2cpp_class_from_name=1  il2cpp_class_get_method_from_name=1  il2cpp_domain_get=1
il2cpp_domain_assembly_open=1  il2cpp_field_get_offset=1  il2cpp_string_new=1  il2cpp_thread_attach=1
il2cpp_ 前缀唯一名（^...$ 全匹配）= 237
```

**但「有字符串」≠「有导出符号」**（自写 ELF 解析，走 `PT_DYNAMIC`→`DT_SYMTAB/DT_HASH`，不依赖被篡改的 section header）：

```
DT_HASH nbucket=2647 nchain(=符号总数)=2647；GLOBAL 2646；能解析出名字的 2646
其中 il2cpp_* 符号数 = 0        ← 七个逐个查全部 MISS
il2cpp_* 名字共 245 处：241 处集中在 .dynstr 内一段连续名字池（首 36,752,639），
                         不被任何 dynsym 项引用；另 4 处（il2cpp_init/runtime_invoke ×2）
                         在文件尾 0x1024C000 段
附带：标准 sanity `AF 1B B1 FA` 在 libil2cpp.so 内 0 命中（所以「so 里没有 magic」不能作为保护证据）
section 头异常：.dynsym 未出现在任何段的 section 映射里，sh_info=1（readelf 报 "local symbol 2647 …"），属 ELF 头层混淆
```

**判定**：这 7 个 API **不是导出符号**，只是被塞进 `.dynstr` 的名字池（241/245 成簇），任何按名解析（`dlsym`/`xdl_sym`）在本 APK 上**大概率拿不到**。
**冲突必须真机验证**：AzusaBA 走 `xdl_sym(handle, "il2cpp_*")`（`il2cpp-api-functions.cpp:18-27`）+ `Il2CppApiReady()` 全非空才装 hook（`main.cpp:1724-1735`）。若线上包与本 APK 一致，日志应出现 `api not found …` 与「il2cpp 符号始终未就绪，放弃安装 hook」。**本轮只读、未跑设备，标未验证**；若属实，唯一回落是硬编码偏移/特征码扫描（版本一升即失效）。

## 三、风控阈值字段归属（grep -o ±40 字符）

源：`$WS/audit/ba-apk/out/metadata-strings.txt`（768,396 行）。每行恰好一个名字，故 ±40 只能取到 `get_` 前缀（本身就是证据：FlatBuffers 生成器同时产出 `get_X` 属性与 `X` 槽位名）。

| 字段 | 命中 | 行号（getter / 槽位） | ±40 实测 |
|---|---|---|---|
| AllowedMaxTimeScale | 3 | 60752 / 60875 | `get_AllowedMaxTimeScale`、`AllowedMaxTimeScale` |
| MinimumClearTime | 8 | 60743 `get_minimumClearTime`、60744 / 60871 | `get_MinimumClearTime` |
| ArenaMinimumClearTime | 3 | 60758 / 60878 | `get_ArenaMinimumClearTime` |
| CheckCheaterMaxUseCostNonArena | 3 | 60748 / 60873 | `get_CheckCheaterMaxUseCostNonArena` |
| CheckCheaterMaxUseCostArena | 3 | 60750 / 60874 | `get_…Arena` |
| CheckCheaterMaxUseCostMultiFloorRaid | 3 | 60807 / 60901 | `get_…MultiFloorRaid` |
| ExcessiveTouchCheckTime | 3 | 60809 / 60902 | `get_ExcessiveTouchCheckTime`（伴 `ExcessiveTouchCheckCount`@60903） |
| AddMinimumClearLevelGap | 1 | 60971 | `AddMinimumClearLevelGap`（仅 builder Add，无 getter） |

所属表（同一连续区 60,625–61,100）：`60625 ConstCombatExcelTable / 60626 GetRootAsConstCombatExcelTable / 60627 Create… / 60628 Start… / 60629 End… / 60630 Finish…Buffer / 60631 FinishSizePrefixed… / 60632 ConstCombatExcel` —— FlatBuffers C# 生成器的完整五件套 + Add*/get_* 成对，邻表同样是 `ConstAudioExcelTable / ConstCommonExcelTable / ConstConquestExcelTable …`。
**归属结论：`ConstCombatExcel`（Excel 主数据表，FlatBuffers 生成类）**，不是 DTO、不是服务器通知（`ServerNotification` 在 73,478–73,535，相距 1.3 万行）。

性质分档（按证据强度）：

1. **不是编译期硬编码常量**（高置信）：字段是 FlatBuffers 表属性；metadata 里没有对应数值字面量；`libil2cpp.so.txt` 对这些名字 0 命中、jadx 源码 0 命中 → 名字只活在 metadata 的 IL2CPP 元数据里，值来自序列化表缓冲区。
2. **表数据来自「主数据/热更」通道，客户端只做本地读取**（中置信）：`MX-Data-Excel-ClientSQLiteConnector-*` 与 `MX-Data-Excel-ServerSQLiteConnector-*` 并存，`GetDatabaseFilePath` / `GetDatabaseFilePathInBuildOriginal` / `…InBuildCopy`、`TableVersion`、`manifest.db` / `dbf.db` → 有「包内原始库 + 可更新副本 + 版本号」三件，典型 master data（服务端下发、客户端落 SQLite）。
3. **客户端本地判定用**：`CheckCheaterMaxUseCost{NonArena,Arena,MultiFloorRaid}` 三场景独立槽 + `ExcessiveTouchCheckTime/Count` 成对 + `AllowedMaxTimeScale`/`MinimumClearTime`，是「清关时长/时间缩放/消耗/触点频率」四类本地风控系数的形状。
4. **服务端是否用同一组阈值二次校验：未验证**（纯静态拿不到；`AccountReportXignCodeCheaterRequest/Response` 说明客户端有上报通道，但上报内容与判定阈值无静态绑定证据）。
5. **默认数值：已取到（2026-11-11 补测，详见 `audit/api-probe.md` §3）**：客户端首启下载的 `TableBundles/16300795542385574620_608d0dfcc14694f5df3d0f6c9dc4c170!constcombatexceltable.bytes`（1032 B，FlatBuffers，89 槽）解出：`MinimumClearTime=10`、`ArenaMinimumClearTime=4`、`AllowedMaxTimeScale=20000(÷1e4=2.0)`、`CheckCheaterMaxUseCostNonArena/Arena/MultiFloorRaid=200/230/200`、`ExcessiveTouchCheckTime=1.0f`、`ExcessiveTouchCheckCount=10`。本地副本 `audit/ba-work/_probe/constcombat.bytes`。这证明「值不在 metadata，而在下载的主数据表」。

## 四、给团队的 3 条影响 / 未验证清单

1. 任何「按类名/方法名反射」的功能在本包可行（名字明文），但**前置的 7 个 API 解析方式必须真机 logcat 取证**：`strings 有名字` 已被证明不等于 `dynsym 有导出`（0/2647）。
2. 阈值类功能不要做「改客户端常量」：字段属于服务端下发的主数据表，客户端改数值只影响本地判定，服务端判定未知；可做的是**读表值**（运行时反射 `ConstCombatExcel`）来自校准 dev 阈值。
3. `global-metadata.dat` 不值得投人力做解密：名字明文已足够支撑按名解析，头部还原只服务于「静态 dump 偏移表」这一条收益有限的路线。
4. 未验证：Il2CppDumper 实跑结果（mono 6.8 在，缺 Il2CppDumper 可执行文件）；设备端 `xdl_sym` 是否真失败；`ConstCombatExcel` 已证来自**下载的 TableBundles**（外部 files，非包内 InBuild），但 InBuild 原版是否同值未比对；服务端阈值二次校验。
