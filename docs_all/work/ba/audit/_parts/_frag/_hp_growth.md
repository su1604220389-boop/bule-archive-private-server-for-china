# 域6 / 域8 / 域9 —— IL2CPP hook 候选符号表（只读取证）

作者：hp-growth（第3层，上级 hookpoint-scout）
数据源（只读，未解包 APK、未联网、未安装/未启动游戏）：
- `M` = `audit/ba-apk/out/metadata-strings.txt`（768396 行）
- `L` = `audit/ba-apk/out/strings/libil2cpp.so.txt`（77730 行）
- `J` = `audit/ba-apk/jadx/sources`（Java 3255 个 .java，仅用于域9 层级对照）

## 0. 方法学与置信度校准（先读这段，否则表的置信度不好理解）

1. **`grep -c` 是原始计数，约为真实符号数 2 倍**（camelCase / PascalCase 成对）。本报告一律写原始计数，并额外给出「精确名」计数（`-F '完整符号0'`，命中 1 即为该符号唯一存在）。
2. 本轮最大收获：metadata 里存在**带命名空间、用 `-` 代替 `.` 的扁平名**，形如
   `MX-Data-CharacterData-GetRequiredExpToLevelUp0`
   → 直接给出 **完整命名空间 `MX.Data.CharacterData` + 方法 `GetRequiredExpToLevelUp`**，信息量远高于裸方法名。这是本报告的主要取材方式。
3. **校准（重要）**：我用「现网 AzusaBA 已确认可用的 hook」反查 metadata，全部命中且行号唯一，证明本表取材方式与线上模块的实际解析路径一致：
   | 现网 hook（`audit/orig_backup/jni/main.cpp`） | metadata 证据 |
   |---|---|
   | `MemoryLobbyData_InitializeCommon` | `MX-Data-MemoryLobbyData-InitializeCommon0` @ **162029** |
   | `CharacterData_InitializeCommon` | `MX-Data-CharacterData-InitializeCommon0` @ **161630** |
   | `SpineBaseAwake` / `SpineBaseOnEnable` | `SpineBase-Awake0` @ **128383** / `SpineBase-RunOnEnableOnce0` @ **128927** |
   | `EntityVisualAwake/Start` | 类名 `EntityVisual` @ **25009**（类名与方法名是两条独立字符串，故 `EntityVisualAwake` 合并串命中 0） |
   → 结论：**「合并串 0 命中」≠ 符号不存在**。`CharacterVisualLateUpdate` / `SpineAnimLateUpdate` / `EntityVisualAwake` 在 M 与 L 中合并串均 0 命中，但类名与方法名分别存在（`CharacterVisual` 149、`LateUpdate` 105、`EntityVisual` 16、`Awake` 698），线上模块正是用「类名+方法名」二元组解析的。后续做新 hook 也必须按二元组拼，不要搜合并串。
4. `>` 行首 FlatBuffers 残留已忽略。`L`（libil2cpp.so）实测**不含托管类名**：`CharacterVisualLateUpdate` / `SpineAnimLateUpdate` / `EntityVisualAwake` / `MemoryLobbyData` / `InitializeCommon` 在 L 中全为 0，故 `L` 在本报告中不承担任何类名证据。
5. 环境：仅写 `/tmp/be.txt`、`/tmp/flat.txt` 两个中间产物（命令内重定向，非工作区文件），工作区只落盘本文件。

---

## 1. 域6 成长（等级 / 经验 / 装备 / 属性上限）

### 1.1 必查关键词原始命中数（`grep -c -F`）

| 关键词 | 命中数 | 判读 |
|---|---|---|
| CharacterData | 141 | 真实存在于 `MX.Data.CharacterData`（命名空间内 117 条扁平名） |
| Equipment | 1006 | 大类，含 Excel/ItemData/Service 多层 |
| ItemDB | 39 | **非 0**：`get_ConsumedItemDBIdAndCount` 等 |
| LevelUp | 335 | 真实 |
| Exp | 2081 | 极常见，需限定 |
| StatLimit | 39 | 真实，FlatBuffers `CharacterStatLimitExcel` |
| CharacterDB | 175 | **非 0**：`GetCharacterDBs`、`MX.GameLogic.DBModel.*` |
| EquipmentDB | 42 | **非 0**：`MX.GameLogic.DBModel.EquipmentDB` |

> 纠偏：任务给的「`ItemDB`/`CharacterDB`/`EquipmentDB` 这类 DB 后缀大概率 0 命中」**不成立**。三者均命中，且 `EquipmentDB` 还带出真实命名空间 `MX.GameLogic.DBModel.EquipmentDB`（证据行 27769：`System.Collections.Generic.IEnumerator<MX.GameLogic.DBModel.EquipmentDB>.get_Current`）。`CharacterExcelTable` 才是 0 命中（283 命中的是 `CharacterExcel`，无 `Table` 后缀变体），`LevelUpResult` 也是 0。

### 1.2 候选符号表

| 候选符号 | kind | 命中数 | 行号样本 | 语义推断 | 用途分类 | 置信度 |
|---|---|---|---|---|---|---|
| `MX.Data.CharacterData.GetLevelExpData` → `MX-Data-CharacterData-GetLevelExpData0` | 方法 | 1（精确）；命名空间 CharacterData 117 | 133097 | 取当前角色的「等级+经验」记录对象，成长域唯一聚合入口 | 数值 | 高 |
| `MX.Data.CharacterData.GetRequiredExpToLevelUp` | 方法 | 1；117 | 130593 | 当前等级升到下一级所需经验 | 数值 | 高 |
| `MX.Data.CharacterData.GetCharacterMaxLevel` | 方法 | 1；117 | 130590 | 角色等级上限（配合自定义等级开关） | 数值 | 高 |
| `MX.GameLogic.Service.CharacterDBService.LevelUpCurrencyRequired` | 方法 | 1；CharacterDB 175 | 133101 | 升级所需货币结算 | 结算 | 中 |
| `CharacterObject-CanLevelUp0` | 方法 | 103（`CharacterObject-` 命名空间）；1 精确 | 133095 | UI 层「可升级」判定，红点也复用（`RedDotService-CanCharacterLevelUp0` @130518） | 流程 | 高 |
| `CharacterObject-GetTotalExpBaseLevelToMaxLevel0` | 方法 | 1；103 | 133100 | 从基底到满级的总经验跨度 | 数值 | 中 |
| `CharacterObject-GetExpRatio0` | 方法 | 1；103 | 133096 | 当前经验条比例 | 只读观察 | 高 |
| `EquipmentObject-CanLevelUp0` / `EquipmentObject-CanTierUp0` | 方法 | 1 / 1 | 135855 / 130627 | 装备升级 / 装备升阶判定 | 流程 | 高 |
| `EquipmentObject-GetTotalExpBaseLevelToMaxLevel0` | 方法 | 1 | 135861 | 装备满级总经验（与角色侧结构对称） | 数值 | 中 |
| `MX.Data.EquipmentItemData.GetRequiredExpToLevelUp` | 方法 | 1 | 135840 | 装备升级经验 | 数值 | 高 |
| `MX.Data.Excel.EquipmentStatExcel.get_LevelUpFeedAddExp` / `get_LevelUpFeedCostAmount` | 字段 | 1 / 1 | 135844 / 135868 | FlatBuffers 配置：喂料加经验 / 喂料消耗量 | 数值 | 中 |
| `CharacterStatLimitExcel` / `GetRootAsCharacterStatLimitExcel` | 类 | 36（StatLimit） | 98417 / 98418 | 属性上限配置表，`ConstCombatExcel` 同族 FlatBuffers，块起于 98417 | 数值 | 中 |
| `RefrehsLevelExp`（游戏内原拼写，非 typo 笔误） / `SetLevelExp` | 方法 | 1 / 1；LevelUp 335 | 149063 / 57055 | **现网模块已 hook 的等级显示刷新点**，非真实成长结算 | 只读观察 | 高 |
| `EquipmentItemLevelUpRequest` / `CharacterLevelUpResponseMessage` | 类 | 1（`LevelUpRequest`）/ 1 | 73956 / 29513 | 升级请求 DTO / 升级响应消息，协议层 | 流程 | 中 |

行数：13 行数据。

【最佳 hook 点建议】域6：**优先 `MX-Data-CharacterData-GetRequiredExpToLevelUp0`（130593）与 `MX-Data-CharacterData-GetLevelExpData0`（133097）做 Dobby inline hook**——二者是「等级/经验」的唯一真值入口，且 `CharacterData` 已被现网 `CharacterData_InitializeCommon`（161630）证明可稳定解析到类，无需新增解析路径；`GetRequiredExpToLevelUp` 返回标量，inline hook 只需改返回值寄存器（arm64 上 X0），实现成本最低、与现有 `old_*` 通道完全同构。`CharacterObject-CanLevelUp0`（133095）/`EquipmentObject-CanLevelUp0`（135855）是 UI 判定，适合做「显示层放行」但**不能改真实等级**，只能按名反射读字段 + 返回值改写。`CharacterStatLimitExcel`（98417）是 FlatBuffers 常量表，**不适合 inline hook**（会被 `CreateCharacterStatLimitExcel`/`GetRootAs…` 复用到多份实例），应走「反射读表字段 + 在 stat 写入侧覆盖」；`get_LevelUpFeedAddExp` 这类 `get_` 字段同理，只宜按名反射读。真实等级写入不在本表可证范围内（`SetLevel` 未出现在 `CharacterData` 命名空间），若要写等级须改走 `BattleEntityStat-SetValue`（见域8）或内存直写 DBModel，风险等级更高。

---

## 2. 域8 敌方 / 自动战斗

### 2.1 必查关键词原始命中数（`grep -c -F`）

| 关键词 | 命中数 | 判读 |
|---|---|---|
| Enemy | 592 | 极常见，仅统计不深入罗列 |
| Boss | 1241 | 含 `ScenarioBoss`/`RaidBoss`/BGM |
| Raid | 4335 | 含 `InteractiveWorldRaid`/`EliminateRaid` 等大子系统 |
| Arena | 806 | 真实 |
| **AutoBattle** | **0** | **该名字不存在**，须换词 |
| **TacticsAI** | **0** | **该名字不存在**（`Tactics` 复数也是 0，只有单数 `Tactic` 615） |
| TacticEntityType | 30 | 真实枚举 |

补充变体实测：`BattleAI`=0、`AutoMode`=0、`Tactics`=0、`BattleAuto`=0，但 `Auto`=697、`AutoTarget`=13、`SkipBattle`=16、`BattleSkip`=7、`AutoPlay`=3、`EnemyExcel`=14、`RaidBoss`=425、`BossPhase`=13、`EnemyStat`=2。
→ **「自动战斗」在托管层的真实命名是 `AutoUse` / `AutoTargeting`，不是 `AutoBattle`；「战术/AI」命名是 `Tactic*`，不是 `Tactics*`。** 这是域8 搜不到东西的唯一原因。

### 2.2 候选符号表

| 候选符号 | kind | 命中数 | 行号样本 | 语义推断 | 用途分类 | 置信度 |
|---|---|---|---|---|---|---|
| `MX.Logic.Battles.Battle.Update` → `MX-Logic-Battles-Battle-Update0` | 方法 | 1；`MX-Logic-Battles-Battle-` 155 | 139463 | 战斗主循环 tick，自动战斗/加速的总闸 | 流程 | 高 |
| `MX.Logic.Battles.Battle.ProcessEntityUpdate` | 方法 | 1；155 | 139406 | 逐实体更新（含敌方行为推进） | 流程 | 高 |
| `MX.Logic.Battles.Battle.ProcessEntityPassiveUpdate` | 方法 | 1；155 | 139417 | 被动技能/光环结算 | 结算 | 中 |
| `MX.Logic.Battles.Battle.get_CurrentGameTimeFrame` / `get_RemainGameTimeFrame` | 方法 | 1 / 1 | 138355 / 138356 | 战斗已用/剩余时间帧（超时判定） | 数值 | 中 |
| `MX.Logic.BattleEntities.BattleEntityStat.SetValue` | 方法 | 1；`BattleEntityStat-` 7 | 129335 | **任意战斗实体属性写入**（敌我通用） | 数值 | 高 |
| `MX.Logic.BattleEntities.BattleEntityStat.SetMinMaxValue` | 方法 | 1；7 | 129338 | 属性上下限钳制 | 数值 | 高 |
| `MX.Logic.Battles.PlayerSkillCardManager.get_IsAutoUse` / `SetAutoUse` | 方法 | 1 / 1；该类 36 | 138211 / 138212 | **自动使用技能卡开关（真正的自动战斗开关）** | 流程 | 高 |
| `MX.Logic.BattleEntities.EntityTargetFinder.FindSupporterCandidates` | 方法 | 1；该类 29 | 138256 | 自动选目标候选集（含 `IsMatch0..5` @138262+） | 流程 | 中 |
| `MX.Logic.BattleEntities.SubPartsRaidBossCharacter.SetSubPartsHP` | 方法 | 1 | 138657 | Raid Boss 部位 HP，削 Boss 最直接 | 数值 | 高 |
| `MX.Logic.BattleEntities.DummyRaidBossCharacter.HandleDamageProcessedEvent` | 方法 | 1 | 157485 | Boss 伤害结算事件 | 结算 | 中 |
| `SwitchBossPhase` | 方法 | 1；BossPhase 13 | 20829 | Boss 阶段切换（另见 `GetRaidBossPhaseForRaid` @80570） | 流程 | 中 |
| `TacticEntityType`（`MX.Data.Excel.CharacterExcel.get_TacticEntityType`） | 枚举/字段 | 30 / 1 | 36567 / 129336 | 实体阵营-类型分类，敌我判别依据 | 数值 | 中 |
| `ArenaObject-Initialize0` / `EliminateRaidObject-IsSeasonOpen0` | 方法 | 34 / 31 | 134399 / 136254 | 竞技场与限时 Raid 的进度/开放判定 | 只读观察 | 中 |

行数：13 行数据（`Enemy` 592 命中按要求未逐条罗列，仅取 3 条代表：89802 `get_EnemyStateMachine`、89803 `EnemyStateMachine`、146231 `UIEnemyInfoAdvantage-DamageAttributeToString0`）。

【最佳 hook 点建议】域8：**自动战斗用 `MX-Logic-Battles-PlayerSkillCardManager-get_IsAutoUse0`（138211）做 inline hook 改返回值（强制 true）**——这是真正的「自动」语义所在，比去碰 `Battle.Update` 安全得多；**加速/加速倍率用 `Battle-Update0`（139463）**，但它每帧被调用，inline hook 必须是极轻量实现（只做计数器/直通），否则掉帧；**敌人削弱走 `BattleEntityStat-SetValue0`（129335）**，该函数是敌我通用的属性写入口，可在 hook 内按 `TacticEntityType`（36567）判敌我后再按比例缩放，避免误伤我方——这条与现网 `get_CurrentStat_Hook` 属同类但**层次更深**（现网改的是 valueTable 快照，这里改的是写入源）。Boss 专杀可用 `SetSubPartsHP0`（138657）。`TacticEntityType`（枚举）、`GetRaidBossPhaseForRaid`（80570）、`ArenaObject-Initialize0` 只能按名反射读值，不适合 inline hook。**0 命中风险提示：`AutoBattle`/`TacticsAI`/`BattleAI`/`AutoMode` 全部 0，任何按这些名字写的 hook 必然解析失败，不要写进代码。**

---

## 3. 域9 大厅 / UI 对照（已有 hook，仅作对照）

### 3.1 必查关键词原始命中数（`grep -c -F`）

| 关键词 | 命中数 | 判读 |
|---|---|---|
| MemoryLobby | 84 | 真实（`MemoryLobbyData` / `MemoryLobbyExcel` / `UIMemoryLobbyDirecting`） |
| CharacterVisual | 149 | 真实，`CharacterVisual-` 扁平名 101 条 |
| EntityVisual | 16 | 真实（类名 @25009 + `EntityVisualFactory` @25170 + `EntityVisualService` @30761） |
| SpineAnim | 15 | 只以 `PlaySpineAnimation` / `EnqueueSpineAnimation` / `ShowLobbySpineAnimationSaveData` 形式出现；**无 `SpineAnim` 类**（`SpineAnim-` 扁平名 0） |
| ModelLobby | 0 | 不存在 |
| LobbyCharacter | 52 | 真实；但 `LobbyCharacter-` 扁平名 0（非扁平名命名风格） |
| CharacterSpine | 15 | 真实（`SetupCharacterSpine` @38826、类 `CharacterSpine` @38961） |
| SpineAnimator | 0 | 不存在 |
| SpineSkin | 1 | 仅 1，边缘 |
| CharacterModel | 1 | 仅 1，边缘 |
| NpcLobby | 0 | 不存在 |
| LobbyCharacterSlot | 0 | 不存在 |

### 3.2 候选符号表

| 候选符号 | kind | 命中数 | 行号样本 | 语义推断 | 用途分类 | 置信度 |
|---|---|---|---|---|---|---|
| `MX.Data.MemoryLobbyData.InitializeCommon` → `MX-Data-MemoryLobbyData-InitializeCommon0` | 方法 | 1；MemoryLobby 84 | 162029 | **现网 hook 点**，大厅数据初始化 | 流程 | 高（线上已验证） |
| `MX.Data.MemoryLobbyData.Get` | 方法 | 1 | 128847 | 大厅数据取用 | 只读观察 | 高 |
| `TryGetMemoryLobbyExcelByIndex` | 方法 | 1 | 31377 | **现网 hook 点**，按下标取大厅 Excel（解锁全大厅用） | 只读观察 | 高（线上已验证） |
| `MemoryLobbySpineLoadInfo` | 类 | 1 | 31376 | 大厅 Spine 加载信息载体 | 只读观察 | 中 |
| `SetMemoryLobbyParcelTexture` | 方法 | 1 | 31477 | 大厅包裹贴图设置 | 流程 | 中 |
| `CharacterVisual-PlayAdaptionEmoji0` | 方法 | 1；`CharacterVisual-` 101 | 133227 | 大厅角色表情动作 | 流程 | 中 |
| `CharacterVisual-CoPlayIdle0` | 方法 | 1；101 | 133213 | 双人/协作待机动作 | 流程 | 中 |
| `CharacterVisual-TimelineSetup0` | 方法 | 1；101 | 133248 | Timeline 装配（替换大厅角色的落点） | 流程 | 中 |
| `CharacterVisual-StopPlayerSkillTimeline0` / `StopPlayerSkillCutinTimeline0` | 方法 | 1 / 1；101 | 133352 / 133354 | 技能演出打断 | 流程 | 中 |
| `EntityVisual`（类） | 类 | 16 | 25009 | **现网 hook 的宿主类**（`EntityVisualAwake/Start` 由此二元组解析） | 流程 | 高（线上已验证） |
| `SpineBase-Awake0` / `SpineBase-RunOnEnableOnce0` | 方法 | 50（`SpineBase-`）；1 / 1 | 128383 / 128927 | **现网 hook 点**，战斗/大厅骨架捕获（倒立、缩放、移速可视化的基础） | 流程 | 高（线上已验证） |
| `SpineBase-PlayTalkAnimation0` | 方法 | 1；50 | 128407 | 语音动作播放 | 只读观察 | 中 |
| `MX.Data.Excel.MemoryLobbyExcel.get_*`（如 `get_LocalizeEtcId`） | 字段 | 1 | 128848 | FlatBuffers 大厅配置字段 | 数值 | 中 |

行数：13 行数据。

【最佳 hook 点建议】域9：**不要再新增机制**——`MX-Data-MemoryLobbyData-InitializeCommon0`（162029）与 `TryGetMemoryLobbyExcelByIndex`（31377）已是现网可用 hook，`SpineBase-Awake0/RunOnEnableOnce0`（128383/128927）也已覆盖骨架捕获；新增大厅类功能应**复用这三个点**，只在其 hook 体内追加逻辑（现网 `main.cpp` 正是这么做的：`CharacterVisual_LateUpdate_Hook` 里链式调用 `TrackSpineBase` + `ApplyLookToEntity`）。若需「替换大厅角色」，`CharacterVisual-TimelineSetup0`（133248）比 `LateUpdate` 更早、更贴近装配期，适合 inline hook；`CharacterVisual-PlayAdaptionEmoji0`（133227）适合表情类改动。`MemoryLobbyExcel.get_*` 与 `MemoryLobbySpineLoadInfo` 只能按名反射读字段。

**与现有 Java 层 hook 的关系（关键结论，须纠正任务前提）**：现网 hook **不是 Java 层**。证据：
1. `audit/orig_backup/jni/main.cpp`（4765 行）内是 `static void (*old_MemoryLobbyData_InitializeCommon)(void*)` @989、`old_CharacterVisualLateUpdate` @625 这类 **Dobby 风格 inline hook 的旧函数指针**，走 `il2cpp_class_from_name` 解析——纯 Native（il2cpp）通道。
2. Java 侧 `jadx/sources` 对 `MemoryLobby`、`CharacterVisual`、`SpineAnim` 三种 `grep -rl -F` **全部返回空**（0 个 .java 文件命中）。dex 里不存在这些类，Java 层没有、也不可能有对应 hook。
3. 因此「能否下沉到 Native」这个问题不成立：**它已经在 Native，且只可能在 Native。** 域9 的所有候选与现有 hook 是**同一机制（il2cpp 类名+方法名二元组 + inline hook）的同一张表**，不存在 Java/Native 双实现或分层错位风险。反过来说，任何试图在 Java 层做大厅/Spine 功能的想法都不可行。

---

## 4. 给汇总方的三条硬结论

1. **命名空间可达性是本轮最大杠杆**：`MX-Data-…` / `MX-Logic-…` / `MX-GameLogic-…` / `MX-SaveData-…` 扁平名把「类名+方法名」一次性给出，应用它反查可把置信度从「猜」提到「证」。建议 `hookpoints.md` 统一按 `MX-<命名空间>-<方法>0` 记录，而不是记裸方法名。
2. **必须剔除的错误关键词**（实测 0 命中，写进代码必然 hook 失败）：`AutoBattle`、`TacticsAI`、`Tactics`、`BattleAI`、`AutoMode`、`CharacterExcelTable`、`LevelUpResult`、`GrowthType`、`ModelLobby`、`SpineAnimator`、`NpcLobby`、`LobbyCharacterSlot`。
3. **反直觉的非 0 关键词**（勿按经验删掉）：`ItemDB`(39)、`CharacterDB`(175)、`EquipmentDB`(42) 均真实存在，`EquipmentDB` 还带出 `MX.GameLogic.DBModel.EquipmentDB`。
