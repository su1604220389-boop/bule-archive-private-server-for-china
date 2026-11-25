## 四、Top10 功能清单（实现层 / hook 点 / UI 开关 / 服务端风险）

> 本节是「下一版该做什么」的排序结论，**不是**随便列的愿望单：每条都给出可落地的 hook 类.方法（来自 metadata 里 `MX-` 生成名，见 §3.0 与 `$WS/audit/ba-apk/out/mx-names.txt`）、UI/配置挂载点（沿用现有工程约定）、以及服务端是否会把改动抹掉。
> 命名提醒：`MX.*` **就是真实 IL2CPP 命名空间**——现有模块已在用 `MX.Logic.BattleEntities`（`main.cpp:1868` 的 `get_TacticEntityType` 解析、1872-1890 的指纹类查找），且 `main.cpp:1270-1273` 的 dump 注释直接写着 `MX.Logic.Battles.DamageResult Damage @ 0x18`。`mx-names.txt` 里尾部的 `0/1/2` 是同名重载消歧后缀，不是方法名。**新引入的类（DamageCalculator 等）仍需真机跑一次 `il2cpp_class_from_name` 探测确认**（返回 null 即名字不对，不会崩）。

### 4.0 三条贯穿全表的工程约定（复用现有基建，别另起炉灶）

1. **UI**：`ToggleSwitch(label,&bool)`（`main.cpp:2470`）+ `ImGui::SliderInt("##id",&v,min,max)`；战斗分组在 `main.cpp:3035-3060`。新增开关必须同时进 `main.cpp:2824` 的能力提示文案（否则用户看不见）。
2. **配置**：新字段写 `Config.h` 的 `battle` 结构（现有 `enableDamageMult/damageMultiplier` 模式，`Config.h:18-26`）→ `Config.cpp` key 表 → **`kCfgVersion` 9→10**（`Config.cpp:43`）。漏 version 会让老配置被改名备份、用户设置全丢（§1.5.4 已记）。
3. **通道选择**：改数值 → 优先 `ApplyStatMods` 的 `switch(key)`（§1.5.3）；改伤害 → 新增 `DamageCalculator.CalcDamage` 单入口 hook；**绝不把倍率同时加在属性表和伤害函数两层**（P0-6 mult² 教训，`main.cpp:1349-1351`）。

### 4.1 Top10 排序表

| # | 功能 | 实现层 | hook 点（类.方法 + 证据） | UI 开关 / 配置 | 服务端风险 | 判定 |
|---|---|---|---|---|---|---|
| 1 | **敌人削弱**（敌 HP/攻击 ×N<1） | Native，复用现有 `get_CurrentStat` hook | 同一函数内加分支即可：`ApplyStatMods` 只对 `type == TT_Student` 生效（`main.cpp:1564`），而 **`IsEnemySide()` 已经写好了却全文件 0 处调用**（`main.cpp:1302`，`grep -n IsEnemySide main.cpp` 只有定义那 1 行）——等于功能写好一半，只差接上 | 开关「敌人削弱」+ 2 个滑条（血量 1-100%、攻击 1-100%）；`enableEnemyNerf/enemyHpPct/enemyAtkPct` | 中：战斗内数值，服务端只看通关结果/用时 | **第一批做**（改动最小、无新反射） |
| 2 | **伤害管线接管**（替换现 `ApplyDamage_Hook`） | Native，Dobby hook 单入口 | 首选 `MX.Logic.Battles.DamageCalculator.CalcDamage`（`metadata-strings.txt:138442`，同类还有 `CalcCriticalChance`:138420 / `IsCritical`:138422 / `CalcApplyDamageRatio`:138435 / `DamageReductionRate`:138434）——纯计算方法、返回值即最终伤害、每次命中调用一次。现用的 `ApplyDamage` 在 `main.cpp:1308` 自己都注明「**从实测看这个函数在 3.0.2 里可能不是主路径**」；真正扣血入口是 `MX.Logic.BattleEntities.Character.ApplyDamage`（`metadata-strings.txt:157427`，另有 `SkillActor.ApplyDamage`:157539，只 hook Character 会漏） | 复用现有「伤害倍率」「锁血」两项 UI，内部改走新 hook | 低-中：只影响单次伤害值 | **推荐**（技术债清理：一处乘倍率，天然消除 mult²） |
| 3 | **必暴击/暴伤** | Native，同一类 hook | `DamageCalculator-CalcCriticalChance0` 返回 1.0；`DamageCalculator-CalcCriticalChance` 旁有 `IsCritical0`、`CalcApplyDamageRatio0`；数值来源表 `CharacterStatExcel` 的 `get_CriticalDamageRate`（`metadata-strings.txt:98254`）、`get_CriticalPoint`（98242）、`get_DodgePoint`（98240） | 开关「必定暴击」+ 滑条「暴击伤害倍率」 | 低：暴击在客户端算 | **推荐** |
| 4 | **技能零费 / CD 清零** | Native | `MX-Logic-Battles-CarrierSkillCard-ForceCoolTimeSet0`（`grep ForceCoolTimeSet` 命中）、`CarrierSkillCard-hasUnlimitedUses0`、`PlayerSkillCardManager-CalculateFrameCost0`、`SkillCard-get_IsCostOverloadEnable0`（`mx-names.txt`） | 开关「技能零费」+ 开关「技能无 CD」；`enableSkillFree/enableSkillNoCd` | **中-高**：`CheckCheaterMaxUseCost{NonArena,Arena,MultiFloorRaid}` 就是按技能使用次数判作弊的字段（§3 风控块），无 CD 会把这个计数打爆 | **做，但默认关闭并给红字警告** |
| 5 | **自动战斗 / 自动用卡** | Native，**游戏自带开关，不用写 AI** | `MX-Logic-Battles-PlayerSkillCardManager-get_IsAutoUse0` / `SetAutoUse0`；配套 `UpdateAutoUseCard0` / `AutoUseBlockTemporarily0` / `get_IsAutoUse`（`mx-names.txt`） | 开关「自动战斗（自动用卡）」；`enableAutoUseCard` | 低：这是游戏自己的功能位，服务端视为正常操作 | **最划算的一条**（一行 setter，替掉「自研战斗 AI」这种高风险大工程） |
| 6 | **战斗时间控制**（冻结计时 / 限幅加速） | Native | 冻结：`MX-Logic-Battles-Battle-get_RemainGameTimeFrame0` / `get_CurrentGameTimeFrame0`（`mx-names.txt`，同类还有 `get_GameState0/set_GameState0`）；加速上限常量 `ConstCombatExcel` `AllowedMaxTimeScale`（`metadata-strings.txt:60875`，getter 60751-60752）、`FastTimeScale`(60864)/`NormalTimeScale`(60863)/`SlowTimeScale`(60868)/`BulletTimeScale`(60865) | 开关「冻结战斗计时」+ 滑条「战斗速度 0.5-2.0×」（**上限写死 `AllowedMaxTimeScale`，不开放无上限**）；`enableFreezeTimer/battleSpeedPct` | **高**：`MinimumClearTime` + `AllowedMaxTimeScale` + `CheckCheaterMaxUseCost*` 同一张表，就是「通关太快/时间缩放超限」的判据；另 `TimelineProcess.lockedTimeScaleByTimeLimit`（`metadata-strings.txt:32712`）/`LockByTimeLimit`(32706) 说明时间轴本身被关卡时限锁 | **只做冻结（不推进计时）+ 限幅加速；无上限加速放弃** |
| 7 | **战斗透视**（敌 HP/属性/技能 CD 只读显示） | Native 只读 + ImGui 绘制 | 读 `BattleEntity`/`EntityStat`（`EntityStat` 命中 51 次）经现有 `get_CurrentStat` 同一路径取；实体枚举 `Battle-FindCharacter0` / `CharacterGroup-GetCharactersInSight0` / `get_CharactersInSightIncludeDead0`（`mx-names.txt`） | 开关「战斗透视」；**默认不落盘**（无副作用，可常开） | **最低**：纯读，不发请求、不改数值 | **推荐先做**（风险≈0，最能体现"面板有用"） |
| 8 | **一键清怪 / 跳波次** | Native | `MX-Logic-Battles-GroundCommandWave-ClearAll0` / `OnEnemyCleared0` / `get_IsClearLastWave0` / `Execute0`（`mx-names.txt`） | 开关「一键清怪」 | **高**：清场后仍要走 `RequestCampaignSubStageResult`（`metadata-strings.txt:43275`）由服务端重算奖励与通关，客户端改的只是本地战斗 | **不做**（放 §五）；最多做「本地演武场测试」 |
| 9 | **掉落/奖励倍率** | Java/Native 都改不了真值 | 结算链是**服务端回包**：`RequestCampaignSubStageResult`(43275) → `CampaignSubStageResultResponseMessage`(29457) → `HandleCampaignSubStageResultResponseMessage`(43281)；胜利侧 `UIVictoryHandler`(57078) 的 `RequestCampaignTacticClearRewards`(57101) 才解出奖励；汇总对象 `MX-Logic-Battles-Summary-BattleSummary0`（`mx-names.txt`） | 若做，只能做「结算页奖励 ×N **仅显示**」；真倍率无 UI 可挂 | **不可行（真改）**：奖励由服务端回包决定，本地乘了也白乘 | **降级为"仅显示"或直接砍**（见 §五.4） |
| 10 | **剧情/演出跳过 + 一键重开** | Native（跳过）+ Java 已有音量键面板 | `canSkipScenario`（`metadata-strings.txt:21345`）、`PlayScenarioSequence`(21343)、`StartScenarioGroupContinuous`(21342)、`RequestEndStage`(21344)（同块属 CCG/演出流程，需按类名复核）；战斗侧 `Battle-Prepare0/Push0` | 开关「自动跳过剧情」+ 按钮「重开本关」 | 低-中：跳过演出是常规功能；**不要**伪造 `RequestEndStage` | **可做**（跳过）；伪造结算请求禁止 |

### 4.2 服务端风险分级（本表用词定义）

- **低**：数值只活在战斗进程内，战斗结束后服务端只验「通关/星级/用时」。改它不产生额外请求、不改结算物品。
- **中**：服务端会统计异常量（用时、技能次数、伤害总量）并与风控字段比对；长期极端值可能进人工/自动复核。
- **高**：结算物品/进度由服务端回包决定（`*StageResultResponseMessage` / `*ClearRewards`），客户端改动会被覆盖，且「客户端显示与回包不一致」本身就是异常特征。

### 4.3 为什么把 1/2/7 排在最前（一句话）

- 1 敌人削弱：**零新 hook**，只加 `ApplyStatMods` 的一个分支，回滚只需关开关；
- 2 伤害单入口：把现有两处乘倍率的坑（P0-6）在结构上消掉，后续所有伤害类功能都只挂一处；
- 7 透视：纯只读，**完全不碰游戏逻辑**，可作为第一批真机验证「新 hook 反射解析是否稳定」的低风险探针。

### 4.4 明确不进 Top10 的（避免重复讨论）

`无限体力/免体力`、`免费抽卡/改抽卡结果`、`邮件/任务一键全领`、`商店免费`、`扫荡免票`、`竞技场改分` —— 全部落在服务端权威侧，理由统一写在 §五.4 / §五.5，不占 Top10 位置。

