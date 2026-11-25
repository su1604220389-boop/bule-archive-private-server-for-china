# global-metadata 字符串 blob 字段定位（blob-locator）

来源（只读，未重新解包）：
- `audit/ba-apk/out/metadata-strings.txt`（768396 行）
- `audit/ba-apk/out/strings/libil2cpp.so.txt`（原始 strings 噪声，命中 0；无语义证据，仅作排除）

## 全局结论（先看这个）

全部 5 个字段（含 CheckCheaterMaxUseCost 的 3 个变体，共 6 个属性）**全部命中**，且**全部落在同一个连续区域 60625–61100**，这是 FlatBuffers C# 代码生成器为一组表生成的代码：

```
60625:ConstCombatExcelTable
60626:GetRootAsConstCombatExcelTable
60627:CreateConstCombatExcelTable
60628:StartConstCombatExcelTable
60629:EndConstCombatExcelTable
60630:FinishConstCombatExcelTableBuffer
60631:FinishSizePrefixedConstCombatExcelTableBuffer
60632:ConstCombatExcel
60633:GetRootAsConstCombatExcel
```

判据（可复核）：`GetRootAs*` / `Create*/Start*/End*` / `Finish*Buffer` / `FinishSizePrefixed*Buffer` 是 FlatBuffers 生成代码的固定签名；全 metadata 里 `GetRootAs` 出现 1032 次、`FinishSizePrefixed` 665 次，即整套数据表（含 ConstCombatExcel）都以 FlatBuffers 形式编进客户端。

该区域的内部排列顺序（同一生成文件的固定节奏）：
1. 60634–60819：`get_x` / `get_X` 成对的 getter 名
2. 60820–60907：PascalCase 属性名清单
3. 60908–60909：`CreateConstCombatExcel` / `StartConstCombatExcel`
4. 60910–61006：`Add*` 变体 setter
5. 61007：`EndConstCombatExcel`
6. 61008–61100+：lowerCamelCase 参数名（`Add*` 的形参）

→ **归属判定：客户端 FlatBuffers 数据表 `ConstCombatExcel`（ClientExcel 常量表，客户端可读，随包内数据文件下发）**，不是服务器 DTO / ServerNotification。
反证：`ServerNotification` 只在 73478 / 73518 / 73519 / 73529 / 73535 出现，与本区域相距约 1.3 万行，中间无交集；本文件内 `ExcelDB` 字样命中 0 次（不要用 ExcelDB 当依据）。

数值默认值：**未取到**。metadata-strings 只有符号名，没有数值字面量；本地 flatbuffer 资源不在本次只读取材范围内。下文不写任何猜测数值。

---

## 1) AllowedMaxTimeScale（3 处，全部命中）

命中行号：
- 60751 `get_allowedMaxTimeScale` / 60752 `get_AllowedMaxTimeScale`（getter）
- 60875 `AllowedMaxTimeScale`（属性名）
- 60974 `AddAllowedMaxTimeScale`（setter）
- 附带形参：61069 `allowedMaxTimeScale`

相邻字段片段（metadata-strings.txt:60868–60876）：
```
60868:SlowTimeScale
60869:AimIKMinDegree
60870:AimIKMaxDegree
60871:MinimumClearTime
60872:MinimumClearLevelGap
60873:CheckCheaterMaxUseCostNonArena
60874:CheckCheaterMaxUseCostArena
60875:AllowedMaxTimeScale
60876:RandomAnimationOutput
60877:SummonedTeleportDistance
60878:ArenaMinimumClearTime
```
推断依据：夹在 `TimeScale` 家族（SlowTimeScale，60868；NormalTimeScale 60863、FastTimeScale 60864、BulletTimeScale 60865）与 `RandomAnimationOutput`/`SummonedTeleportDistance` 之间，属同一战斗常量块；getter/setter/形参三重存在 = 生成代码，不是手写 DTO。
疑似所属：FlatBuffers 表 `ConstCombatExcel`（表包装类 `ConstCombatExcelTable`），字段槽 60875；客户端可读。
语义推测（标注推测，未验证）：客户端允许的最大时间缩放上限，可能用于战斗加速/慢放合法区间校验。

## 2) MinimumClearTime（8 处，全部命中）

命中行号：
- 60743 `get_minimumClearTime` / 60744 `get_MinimumClearTime`
- 60871 `MinimumClearTime`
- 60970 `AddMinimumClearTime`
- 61065 `minimumClearTime`（形参）
- 另 2 处属同名不同字段：60757 `get_arenaMinimumClearTime` / 60758 `get_ArenaMinimumClearTime`，60878 `ArenaMinimumClearTime`，60977 `AddArenaMinimumClearTime`，61072 `arenaMinimumClearTime`（即 `ArenaMinimumClearTime`，与普通 `MinimumClearTime` 是两个独立槽位）

相邻字段片段（metadata-strings.txt:60741–60758，getter 区）：
```
60741:get_aimIKMaxDegree
60742:get_AimIKMaxDegree
60743:get_minimumClearTime
60744:get_MinimumClearTime
60745:get_minimumClearLevelGap
60746:get_MinimumClearLevelGap
60747:get_checkCheaterMaxUseCostNonArena
60748:get_CheckCheaterMaxUseCostNonArena
60749:get_checkCheaterMaxUseCostArena
60750:get_CheckCheaterMaxUseCostArena
60751:get_allowedMaxTimeScale
60752:get_AllowedMaxTimeScale
60757:get_arenaMinimumClearTime
60758:get_ArenaMinimumClearTime
```
推断依据：同一 getter 序列里与 `MinimumClearLevelGap`、`CheckCheaterMaxUseCost*`、`AllowedMaxTimeScale` 紧邻，节奏为「小写 get_ + 大写 get_」成对，典型 FlatBuffers 生成属性；无任何 DTO 命名（无 `k__BackingField`、无 `set_`）。
疑似所属：`ConstCombatExcel` 字段槽（60871）；客户端可读。

## 3) CheckCheaterMaxUseCost 及变体（9 处，全部命中；未合并为单一结构体）

命中行号（元数据里**没有**名为 `CheckCheaterMaxUseCost` 的单一字段/结构体，只有 3 个独立槽位）：
- NonArena：60747 `get_checkCheaterMaxUseCostNonArena` / 60748 `get_CheckCheaterMaxUseCostNonArena`；60873 属性名；60972 `AddCheckCheaterMaxUseCostNonArena`；61067 形参
- Arena：60749 / 60750 getter；60874 属性名；60973 `AddCheckCheaterMaxUseCostArena`；61068 形参
- MultiFloorRaid：60807 / 60808 getter；60901 属性名；61000 `AddCheckCheaterMaxUseCostMultiFloorRaid`；61098 形参

相邻字段片段（metadata-strings.txt:60898–60904）：
```
60898:EchelonExtensionCostRegenRatio
60899:EchelonOverloadCostRegenRatio
60900:EchelonExtensionOverloadCostRegenRatio
60901:CheckCheaterMaxUseCostMultiFloorRaid
60902:ExcessiveTouchCheckTime
60903:ExcessiveTouchCheckCount
60904:CampaignAlertPopupLevelGap
60905:MoveCorrectionSkipRatio
```
推断依据：3 个变体分散在同一个 Pascal 字段清单的不同位置（60873/60874 相邻，60901 靠后），说明是 3 个独立标量槽位，而不是被打包成一个 `CheckCheaterMaxUseCost` 子结构体（若为嵌套 struct，会先出现 struct 类型名 + 内部字段，形如 `get_CheckCheaterMaxUseCost_xxx`）；实测 getter 名直接内联后缀，故为扁平槽位。
疑似所属：`ConstCombatExcel`（60873 / 60874 / 60901 三槽）；客户端可读。
语义推测（标注推测）：按玩法（非竞技场 / 竞技场 / 多层突袭）分档的「作弊检测允许的最大消耗/使用值」阈值。

## 4) ExcessiveTouchCheckTime（3 处，全部命中）

命中行号：
- 60809 `get_excessiveTouchCheckTime`（配对 60810 `get_ExcessiveTouchCheckTime`）
- 60902 `ExcessiveTouchCheckTime`
- 61001 `AddExcessiveTouchCheckTime`
- 附带形参：61099 `excessiveTouchCheckTime`

相邻字段片段（metadata-strings.txt:60805–60816，getter 区）：
```
60805:get_echelonExtensionOverloadCostRegenRatio
60806:get_EchelonExtensionOverloadCostRegenRatio
60807:get_checkCheaterMaxUseCostMultiFloorRaid
60808:get_CheckCheaterMaxUseCostMultiFloorRaid
60809:get_excessiveTouchCheckTime
60810:get_ExcessiveTouchCheckTime
60811:get_excessiveTouchCheckCount
60812:get_ExcessiveTouchCheckCount
60813:get_campaignAlertPopupLevelGap
```
推断依据：与 `ExcessiveTouchCheckCount`（60811/60812、60903）成对出现，是「触摸频率检测」的两个配套常量；同一生成块内紧邻 `CampaignAlertPopupLevelGap`、`MoveCorrectionSkipRatio`。
疑似所属：`ConstCombatExcel`（60902）；客户端可读。

## 5) AddMinimumClearLevelGap（1 处，命中）

命中行号：
- 60971 `AddMinimumClearLevelGap`（唯一的 `Add*` 形式）
- 同一字段的其他形式：60745 `get_minimumClearLevelGap` / 60746 `get_MinimumClearLevelGap`；60872 `MinimumClearLevelGap`；61066 形参 `minimumClearLevelGap`
（字段名 `MinimumClearLevelGap` 本身共 5 处；`AddMinimumClearLevelGap` 只有 60971 一处）

相邻字段片段（metadata-strings.txt:60968–60975，setter 区）：
```
60968:AddAimIKMinDegree
60969:AddAimIKMaxDegree
60970:AddMinimumClearTime
60971:AddMinimumClearLevelGap
60972:AddCheckCheaterMaxUseCostNonArena
60973:AddCheckCheaterMaxUseCostArena
60974:AddAllowedMaxTimeScale
60975:AddRandomAnimationOutput
```
推断依据：`Add*` 是 FlatBuffers builder setter；它与 `AddMinimumClearTime`(60970)、`AddCheckCheaterMaxUseCost*`(60972/60973)、`AddAllowedMaxTimeScale`(60974) 成序列，位置与 Pascal 清单（60871/60872/60873/60874/60875）严格同序 → 同一张表。
疑似所属：`ConstCombatExcel`（60872）；客户端可读。

---

## 最可靠归属结论（供 thresholds.md 引用）

1. 这 6 个属性全部是**客户端 FlatBuffers 常量表 `ConstCombatExcel` 的扁平字段槽**，位于 `audit/ba-apk/out/metadata-strings.txt:60625–61100`；生成签名证据：`GetRootAsConstCombatExcelTable`(60626) / `CreateConstCombatExcel`(60908) / `Add*`(60910–61006) / `EndConstCombatExcel`(61007)。
2. 因此客户端可直接读、也可被改（改包内 flatbuffer 数据即改常量），但**没有任何服务器 DTO / ServerNotification 侧同名字段**可作对端校验依据——证据：`ServerNotification` 仅见于 73478–73535，距本块约 1.3 万行。
3. 未取到任何数值默认值（metadata 无字面量）；如需真值，需另取包内 ConstCombatExcel 的 flatbuffer 资源（本次禁止解包，未做）。

## 待补充/风险
- `MinimumClearTime` 与 `ArenaMinimumClearTime` 是不同槽位，不要合并当同一阈值。
- `CheckCheaterMaxUseCost` 不存在合并结构体，按 3 个玩法档位分别取。
- `strings/libil2cpp.so.txt` 对该 5 字段命中 0（纯噪声 dump），不能用于交叉验证方法名/符号。
