# hp-combat · 战斗数值 + 技能/CD/费用 IL2CPP hook 候选符号表

只读取证，未解包 APK、未联网、未安装/启动游戏。
数据源（唯一依据）：
- `M = audit/ba-apk/out/metadata-strings.txt`（768396 行，`strings -n 4` of global-metadata.dat）
- `L = audit/ba-apk/out/strings/libil2cpp.so.txt`（77730 行）

## 0. 取证方法与计数口径（先看这段再看表）

- 「命中数」= `grep -c -F '<符号>' $M` 的原始数字。**该类名字对出现规律适用**：同一符号通常同时存在 camelCase 与 PascalCase 两条，所以语义上的“1 个方法”常得到 2 左右的原始计数；本表若为 1，说明只保留了扁平名形态。
- 「类」行的命中数不是 `-F` 而是 `grep -c -E '^MX-<ns>-<Class>-'`，即**该类扁平名条数**（类里能数出多少个成员名），已在该行注明。
- 扁平名形态（信息量最高，本次全部证据都来自它）：`命名空间-子类-方法0`，尾部 `0`/`1`/`2` 是**同名重载消歧后缀**，不是方法名的一部分。例：`MX-Logic-Battles-DamageCalculator-CalcDamage0` = `MX.Logic.Battles.DamageCalculator.CalcDamage()`。
- 行首带 `>` 的 FlatBuffers 残留（`>slowTimeScale`）已忽略，未计入任何结论。
- `L` 里**没有任何托管类名**（本次复核：`DobbyHook`=0，只有 `il2cpp_class_from_name`=1、`il2cpp_domain_get`=2、`il2cpp_class_get_method_from_name`=1、`il2cpp_resolve_icall`=1）。所以 `L` 只能证明「il2cpp 运行时解析 API 可用、Dobby 需自己导入（.so 无该导出）」，**不能**当类名证据。

**命名规律推翻了一个前提**：`TacticsEntity` 在 `M` 中 **0 命中**，连 `Tactics` 都是 **0 命中**（全文件）。国服 BA 的实体命名空间不是 Tactics 系，而是：

| 命名空间（扁平名前缀） | 扁平名条数 |
|---|---|
| `MX-Logic-BattleEntities` | 1117 |
| `MX-Logic-Battles` | 1366 |
| `MX-Logic-Skills` | 543 |
| `MX-Data-Excel-*`（FlatBuffers 配置表） | 各表 10~200 |

语义上：`MX.Logic.BattleEntities` = 战斗实体/属性，`MX.Logic.Battles` = 战斗流程与算法（DamageCalculator、LogicEffectProcessor、SkillCard），`MX.Logic.Skills` = 技能与逻辑效果（`MX-Logic-Skills-LogicEffects-*`）。下文 `MX.` 前缀同类写法等同于扁平名里的 `MX-`。

---

## 1. 域1：战斗数值（伤害/属性/Buff/控制/治疗）

| 候选符号 | kind | 命中数 | 行号样本 | 语义推断 | 用途分类 | 置信度 |
|---|---|---|---|---|---|---|
| `MX.Logic.Battles.DamageCalculator` | 类 | 22（该类扁平名条数） | metadata-strings.txt:138393, 138442, 138420 | 伤害计算中枢，命中判定/暴击/减伤/倍率/护甲因子全在这一个类里 | 数值 | 高 |
| `DamageCalculator.CalcDamage` | 方法 | 1 | metadata-strings.txt:138442 | 单次伤害的主计算入口，返回值即最终伤害数值 | 数值 | 高 |
| `DamageCalculator.CalcAttackPower` | 方法 | 1 | metadata-strings.txt:138402 | 由 AttackPower 及各类修正结算出本次攻击力 | 数值 | 高 |
| `DamageCalculator.CalcCriticalChance` / `IsCritical` | 方法 | 1（各1） | metadata-strings.txt:138420, 138422 | 暴击率计算 + 暴击随机判定（Critical 全量118 命中里这两条最贴近判定点） | 数值 | 高 |
| `DamageCalculator.CalcApplyDamageRatio` / `…Ratio2` | 方法 | 1（各1） | metadata-strings.txt:138435, 138436 | 应用伤害倍率（普通/第二套倍率 ApplyDamageRatio2） | 数值 | 高 |
| `DamageCalculator.DamageReductionRate` | 方法 | 1 | metadata-strings.txt:138434 | 减伤率（防御/护甲侧）计算 | 数值 | 高 |
| `MX.Logic.BattleEntities.Character.ApplyDamage` | 方法 | 1 | metadata-strings.txt:157427 | 角色实体真正扣血入口（受击侧），HP 扣减与下限保护都在这 | 结算 | 高 |
| `MX.Logic.BattleEntities.SkillActor.ApplyDamage` | 方法 | 1 | metadata-strings.txt:157539 | SkillActor 形态的扣血入口（技能/分身造成的伤害落地） | 结算 | 中 |
| `BattleEntityStatProcessor.ApplyEffects` | 方法 | 1 | metadata-strings.txt:156834 | 把一批 stat 修改批量写进实体，是 Buff/减益真正生效的落地点 | 数值 | 高 |
| `BattleEntityStatProcessor.CacheInitialStat` | 方法 | 1 | metadata-strings.txt:134054 | 战斗开始时快照初始属性，构成属性基线（改基线最隐蔽） | 数值 | 中 |
| `BattleEntityStat.SetValue` / `SetMinMaxValue` | 方法 | 1（各1） | metadata-strings.txt:129335, 129338 | 单条属性写值（含 min/max clamp），可改 HP/攻击/任意 StatType | 数值 | 高 |
| `LogicEffectProcessor.ProcessStatChangeEffect` | 方法 | 1 | metadata-strings.txt:138471 | 处理 StatChange 类逻辑效果——Buff/减益的主执行通道（StatChange 全量178 命中，这条是执行端） | 数值 | 高 |
| `LogicEffectProcessor.DecideApplyCrowdControl` | 方法 | 1 | metadata-strings.txt:138367 | 决定是否施加群体控制（韧性/免疫判定） | 数值 | 高 |

补充证据（未占表行、供上层取舍）：
- 治疗/护盾：`LogicEffectProcessor-ProcessHealEffect0`（138463）、`ProcessShieldHealEffect0`（138464）、`ProcessDamageEffect0`（138450）——同族方法，行号相邻，说明「伤害/治疗/护盾」是同一 switch 的不同分支。
- 结算结果事件：`DamageResultEventArgs-get_IsCritical0`（158748）、`get_IsNormalAttack0`（158747）、`get_IsDamaged0`（138706）——纯观察点，适合只读。
- Buff 词根污染严重：`Buff` 原始计数 3248，但扁平名中 `^MX-.*Buff` 的 1123 条绝大多数是 **`get_ByteBuffer0`（FlatBuffers！）** 和 `BuffGroupId/Prob`，直接搜 Buff 会得到假的“命中最多的快感”。真正战斗 Buff 走 `HexaBuff`（全量14 命中）：`PlayerGroup-InitHexaBuff0`（138225）、`PlayerGroup-ApplyHexaBuff0/1`（138251/138252）、`ManualSkillProcessor-InitHexaBuff0/ApplyHexaBuff0`（138224/138250）。同族受控效果：`ProcessStatusAddEffect0`（138468）、`ProcessStatusRemoveEffect0`（138470）。
- 建议与 `CrowdControl` 相关的还有 `CharacterStatExcel-get_ExtendCrowdControlDuration0`（129374）——配置侧延长控制时长。
- `Stat` 原始计数 4247 也高度含噪（`Statistics*` 等），做 `-F 'Stat'` 判断必然高估，必须落到 `BattleEntityStat`/`StatChange`/`StatType` 这类复合词。

**【最佳 hook 点建议·域1】** 首选 `MX.Logic.Battles.DamageCalculator.CalcDamage` 做 Dobby inline hook：它是**纯计算方法**，入参是攻击方/受方上下文、**返回值就是最终伤害数字**，hook 后直接改写返回值即可实现全局伤害倍率，不必扫描内存也不需要理解 stat 表结构；调用频率 = 每次命中一次（不是每帧），日志/改写都安全。次选 `MX.Logic.BattleEntities.Character.ApplyDamage`：受击侧入口，可在扣血前读到 damage 实参并 clamp HP（做“不死/锁血”更稳），但要注意它是实体虚方法，需按 `Character` 类名解析再取地址、且 SkillActor/SubPartsRaidBossCharacter 各有同名重载（157539/157569），只 hook Character 会漏掉非角色实体。只能按名反射读的：`DamageResultEventArgs.get_IsCritical`、`BattleEntityStat.get_*`、`BattleEntityStatProcessor.CacheInitialStat`——这些是 getter/基线快照，参数里没有可改的数值、返回值改动影响面广（会污染 UI 与结算事件），只适合反射读取做观察与判定。

---

## 2. 域7：技能 / CD / 费用

| 候选符号 | kind | 命中数 | 行号样本 | 语义推断 | 用途分类 | 置信度 |
|---|---|---|---|---|---|---|
| `MX.Logic.BattleEntities.SkillActor` | 类 | 61（该类扁平名条数） | metadata-strings.txt:138677, 143288, 138671 | 技能的“执行者”，释放/动作注册/形态转换/状态全在它身上，是技能域最重的类 | 流程 | 高 |
| `SkillActor.UseSkill`（0/1/2 三重载） | 方法 | 1（每个重载1） | metadata-strings.txt:138677, 143288, 143289 | 技能真正释放入口，三个重载对应不同入参组合；要 hook 必须三个都挂或按签名挑 | 流程 | 高 |
| `MX.Logic.BattleEntities.Character.CanUseSkill` | 方法 | 1 | metadata-strings.txt:138635 | 技能可用性判定（CD/费用/状态前置闸门），返回 bool | 流程 | 高 |
| `MX.Logic.Battles.SequentialSkillCardManager.UseSkillCard`（0/1） | 方法 | 1（各1） | metadata-strings.txt:138643, 138644 | 顺序自动放卡调度器，自动战斗/自动技能都走这里 | 流程 | 中 |
| `MX.Logic.Battles.SkillCard` | 类 | 48（该类扁平名条数） | metadata-strings.txt:159618, 143252, 159704 | 技能卡运行时对象，费用/CD/目标/卡面状态全封装在此，费用体系的核心类 | 数值 | 高 |
| `SkillCard.CoolTimeComplete` | 方法 | 1 | metadata-strings.txt:159618 | 冷却结束回调（CD 归零瞬间），天然的下手点：可在此立刻重置为可再次释放 | 流程 | 高 |
| `CarrierSkillCard.ForceCoolTimeSet` | 方法 | 1 | metadata-strings.txt:133909 | 强制设置冷却时间，即“CD 可写”的官方入口，改冷却最直接 | 数值 | 高 |
| `SkillCard.GetBaseCost` | 方法 | 1 | metadata-strings.txt:143252 | 取技能基础费用（另有 get_BaseCost 属性在 156891），费用体系的源头 | 数值 | 高 |
| `SkillCard.CalcSet` | 方法 | 1 | metadata-strings.txt:143248 | 费用计算/叠加（配合 MinBaseCost 143254、ConservativeCoeffApply 143250、CalcAdd 143251） | 数值 | 高 |
| `SkillCard.GetCostsFromExcel` | 方法 | 1 | metadata-strings.txt:159704 | 从 SkillExcel 读费用配置进运行时，是“配置→战斗费用”的转换点 | 数值 | 高 |
| `MX.Data.Excel.SkillExcel.get_SkillCost` | 方法 | 1 | metadata-strings.txt:130673 | 技能配置表里的费用字段（同表另有 get_ExtraSkillCost 130672） | 数值 | 高 |
| `MX.Data.Excel.SkillExcel.get_CoolTime` | 方法 | 1 | metadata-strings.txt:133906 | 技能配置表里的冷却字段 | 数值 | 高 |
| `MX.Data.Excel.CharacterStatExcel.get_RegenCost` | 方法 | 1 | metadata-strings.txt:129370 | 角色回费（cost regen）速度配置；同表 get_AmmoCost 129363 | 数值 | 中 |

补充证据（未占表行）：
- 费用变更效果族（同为 `LogicEffectProcessor` 内相邻方法，说明费用变化走统一效果通道）：`ProcessSkillCostChangeEffect0`（138501）、`ProcessExtraSkillCostChangeEffect0`（138502）、`ProcessAddSkillCostEffect0`（138581）、`ProcessCostRegenBanEffect0`（138571）；配套实体侧 `BattleEntity-AttachCostRegenBanEffect0/Remove...`（138567/138568）、`get_IsCostRegenBan0`（138577）、`CostRegenBanEffect-CheckExpired0/Activate0`（138569/138570）。
- 技能卡费用覆盖：`MX-Logic-Skills-LogicEffects-TargetSlotExSkillCostOverrideEffect-GetOverriddenCostAmount0`（134062）、`SkillCard-get_IsCostOverloadEnable0`（143246）、`GetOriginalBaseCost0`（143249）、`GetExtraCost0`（143263）。
- EX 技能：`SkillFactory-IsExSkill0`（134069）、`HeroService-IsExSkillUseBehavior0`（133037）、`ExSkillCardRedrawGaugeEffect`（133296/133297）。全量 `EXSkill`=40、`ExSkillCost`=19、`ExSkillCutIn`=20（有 UI 侧 cut-in 资源名）。
- CD 相邻：`SkillCard-Update0`（159619，每帧更新）、`Battle-Debug_NoCoolTime0`（158718，官方自带的无 CD 调试开关）、`PassiveExecution-get_RemainedCoolTimeNotTriggerFrame0`（160304）。

**【最佳 hook 点建议·域7】** 首选 `MX.Logic.BattleEntities.SkillActor.UseSkill`（三个重载 138677/143288/143289）做 Dobby inline hook：它是方法、参数里带技能与目标上下文、调用频率恰好等于“实际释放技能”的次数（玩家点击或自动放卡，不会被每帧轮询刷爆），可以在进入前改写（费用/目标/强制允许）或在返回后确认释放结果。若只想要“费用归零”这种窄改动，更精准的是 `SkillCard.GetBaseCost`（143252）改返回值——单一返回值、语义干净、不影响 CD 与目标解析；要改 CD 则挂 `CarrierSkillCard.ForceCoolTimeSet`（133909）或 `SkillCard.CoolTimeComplete`（159618）。只能按名反射读的：`SkillExcel.get_SkillCost` / `get_CoolTime` / `CharacterStatExcel.get_RegenCost`——这些是 FlatBuffers 配置表 getter，每次调用都解 buffer，按帧调用代价高，正确用法是**反射读一次拿到配置常量**（或直接读 Excel 表）后自己缓存，不要拿它做热点拦截。

---

## 3. 0 命中 / 名字不同 的关键词（如实记录，未编造类名）

**域1**
| 关键词 | `grep -c -F` | 结论 |
|---|---|---|
| `TacticsEntity` | 0 | 该命名不存在 |
| `Tactics`（放宽到词根） | 0 | 整份 metadata 里没有 Tactics 系命名；实体真名是 `MX.Logic.BattleEntities.*`（1117 条） |
| `TacticsEntityStat` | 0 | 同上；真实属性类为 `BattleEntityStat`（`SetValue` 129335） |
| `BuffDebuff` | 0 | 无此复合词；Buff 侧为 `HexaBuff`/`StatChange`/`StatusAdd` |
| `DodgeRate` | 0 | 闪避率不叫这个；真实线索 `get_DodgePoint`(98250)、`BattleEntity_Dodged`(83611)、`GetTerrainDodgeFactor`(80612) |

其余必查词全部 >0：`Stat` 4247（含噪，见上）、`Buff` 3248（含噪，多为 ByteBuffer）、`Heal` 391、`Critical` 118、`CrowdControl` 94、`MaxHP` 77、`AttackPower` 37、`Dodge` 22、`ApplyDamage` 21、`DamageResult` 10、`CalcDamage` 5、`DamageInfo` 6、`DamageProcess` 21、`CriticalRate` 15、`CriticalDamage` 10、`CrowdControlType` 2、`StatType` 105、`HpRatio` 4、`StatModifier` 3。

**域7**
| 关键词 | `grep -c -F` | 结论 |
|---|---|---|
| `CostRegenTime` | 0 | 无此名；用 Excel 变体命中：`CharacterStatExcel-get_RegenCost0`(129370)、`CostRegenBanEffect-*`(138567~138571) |
| `CostRecover` | 0 | 无此名；回费语义落在 `RegenCost` 与 `ProcessCostRegenBanEffect`（禁用侧） |
| `SkillHandler` | 0 | 无此名；技能执行类真名是 `SkillActor`（61 条）与 `SkillCard`（48 条） |
| `EchelonCost` | 0 | 无此名；费用同义命中 `CommonCost`=20、`ExSkillCost`=19、`SkillCost`=104 |
| `SkillDB` | 2 | 命中只有 `LocalizeSkillDBSchema`(102632) / `SkillDBSchema`(104949)，**是本地化库 schema，不是战斗技能数据**，不可当技能表用 |

其余必查词全部 >0：`CoolTime` 107（扁平名仅 7 条，其中战斗侧 4 条）、`SkillSlot` 147、`SkillExcel` 109、`SkillUse` 65、`CostRegen` 44、`EXSkill` 40、`SkillLogic` 27、`ExSkillCutIn` 20、`SkillCost` 104、`SkillCoolTime` 4。

---

## 4. 置信度边界（务必随结论一起传下去）

1. 以上全部证据只证明「符号名存在于 global-metadata.dat」，**证明不了方法未被内联、不是抽象/接口方法、也无法给出参数签名与重载顺序**。→ 落地前必须在 libil2cpp 侧用 `il2cpp_class_from_name` + `il2cpp_class_get_method_from_name(name, argc)` 解析真实指针，并把 `il2cpp_method_get_param` 的签名 dump 出来核对（`UseSkill` 的 3 个重载尤其必须先查 argc）。
2. 尾部 `0`/`1`/`2` 只是消歧歧后缀，**不保证对应源码里的重载顺序**；本表中的“0/1/2 三重载”是从同名不同后缀推断的重载关系，属于中高置信、需签名确认。
3. `L` 中确认 `DobbyHook`=0 导出，说明 Dobby 需以独立库形式注入/静态链入，不能靠 dlsym 从 libil2cpp 找。
