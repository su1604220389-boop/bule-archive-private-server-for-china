# §三 Native 可 hook 点表（按 9 个功能域，IL2CPP metadata 证据）

> 只读取证。证据源：`audit/ba-apk/out/metadata-strings.txt`（768,396 行，`strings -n 4 global-metadata.dat`）为主，`audit/ba-apk/out/strings/libil2cpp.so.txt`（77,730 行）与 `jadx/sources` 为辅。
> 所有「命中数」= `grep -c -F '<子串>' metadata-strings.txt` 的**原始计数**（大小写敏感子串匹配，非全词）。
> 所有「行号样本」= 真实 `grep -n` 结果的 `metadata-strings.txt:N`，未做任何推测填充。

## 0 方法论与全局前提（先读这节，它决定后面每张表怎么用））

**0.1 不存在「按名字 dlsym 找游戏函数」这条路。** 实测 `libil2cpp.so.txt` 里 **零个托管类名**：`TimeScaleService` / `BattleResult` / `Gacha` 全部 0 命中，只有 `il2cpp_class_get_method_from_name`、`il2cpp_runtime_invoke` 等 `il2cpp_*` 运行时导出。所以任何 hook 都必须是两段式：
`il2cpp_domain_get_assemblies` → `il2cpp_class_from_name(image, ns, name)` → `il2cpp_class_get_method_from_name` → 拿到方法指针 → **Dobby inline hook**。metadata 名字表明文可用，是这条链路唯一的「地图」。

**0.2 名字表分三个区，混用会直接得出错误结论。**
| 区段 | 内容 | 可信度 |
|---|---|---|
| ~20,000–100,000 | 短名区：MonoBehaviour 序列化字段（UI 预制体字段）、属性名、类名混在一起 | 低。**裸词命中 ≠ 存在同名类** |
| ~128,000–145,000 与 ~158,000–170,000 | `类-方法0` / `命名空间-类-方法0` 扁平区（尾部 `0` 是消歧后缀） | **高**。直接给出 C# 全名 + 方法名，是 il2cpp API 的现成入参 |

反例（本表已剔除，但别人容易踩）：`BattleTime` 命中 19 次，其所在行 33393 的邻居是 `VictoryImg` / `DefeatImg` / `StageName` / `RewardPrefab` / `OkButton` —— 它是**结算界面的 UI 文本字段**，不是战斗时钟。

**0.3 最高价值的结构性发现：`MX-Logic-*` 命名空间树共 4,034 条扁平名。**
分布：`Battles`=1366、`BattleEntities`=1117、`Data`=598、`Skills`=543、`Services`=240、`Actions`=158、`AI`=4、`Equipments`=1、`Coroutine`=6。
即游戏逻辑真实命名空间是 `MX.Logic.Battles` / `MX.Logic.BattleEntities` / `MX.Logic.Data` / `MX.Logic.Skills` / `MX.Logic.Services` / `MX.Logic.Actions` / `MX.Logic.AI`。**这是全表最有用的一条**：有了命名空间就能精确调 `il2cpp_class_from_name`，不用遍历所有类。

**0.4 计数不要「除以 2」。** 有些名字确实成对（`get_X` / `get_X` 的 camel+Pascal 变体），但大小写敏感子串会让计数不对齐（`SlowTimeScale`=3 而 `slowTimeScale`=2，因为 `get_slowTimeScale` 里是小写开头）。一律报原始 `grep -c`。

**0.5 FlatBuffers 配置表定位。** 全表 423 个 `*ExcelTable` 名，每张表的块以 `GetRootAs<X>ExcelTable` 开头。实测 `ConstCombatExcel` 块 = **60625–61105**（下界是 61106 的 `GetRootAsConstCommonExcelTable`），比先前记录的「60625–61100」略宽；块内是 `get_字段` / 裸字段名 / `Add字段` 四段式重复。块内字段只是**本地常量**，改它只改本地表现。

---

## 1 战斗数值（TacticsEntity / Stat / ApplyDamage / DamageResult / Buff / CrowdControl / Heal / Critical / Dodge / AttackPower / MaxHP）

<!-- D1 -->

---

## 2 时间与速度（TimeScale / SlowTimeScale / FastTimeScale / BulletTimeScale / BattleTime / AllowedMaxTimeScale）

| 候选符号 | kind | 命中数 | 行号样本 | 语义推断 | 用途分类 | 置信度 |
|---|---|---|---|---|---|---|
| `MX.Logic.Battles.LogicGameTime`（Pause / Resume / SetTimeout / ForceSetFrame / get_TotalSeconds / get_TotalGameTimeSecond） | 类+方法 | 扁平名 6 | 158695, 158697, 158857, 158858 | 战斗逻辑时钟（帧驱动）。提供暂停/恢复/超时/强推帧，是「战斗流程」的主开关 | 流程 | 高 |
| `TimeScaleService` | 类 | 8 | 31331, 128637, 137936 | 战斗时间倍率服务；成员含 `CachedTimeScale` / `IsPaused` / `AudioPitch` / `SetAudioTimeScaleNoCache` | 流程 | 高 |
| `get_TimeScale` / `set_TimeScale` / `TimeScale` | 方法+字段 | 3 | 21290, 21293, 21296 | 服务的「当前倍率」属性，最终作用于引擎时间的最可能真值 | 数值 | 高 |
| `ApplyTimeScale` / `get_ApplyTimeScale` | 方法 | 4 | 21304, 21307 | 把当前倍率下发到引擎/系统的应用点，最像「每帧写入」的收口 | 数值 | 高 |
| `NormalTimeScale` / `FastTimeScale` / `BulletTimeScale` / `SlowTimeScale` / `AllowedMaxTimeScale`（ConstCombatExcel 块内） | 字段 | 块内 25 | 60727, 60731, 60751, 61069 | 配置常量：普速/加速/子弹时间/减速/上限，四段式（getter 60727-60752、裸字段 60863-60875、Add* 60962-60974、字段名 61057-61069） | 数值（本地常量） | 高 |
| `allowedMaxTimeScale` / `AllowedMaxTimeScale` | 字段 | 3 | 60751, 61069, 21322 | 时间倍率**硬上限**，最可能是防加速/防拖时间的读取点 | 数值 | 高 |
| `MX.Logic.Battles.GroundCommandSetTimeScale`（Execute / CoWaitSeconds / Serialize） | 类+方法 | 11 | 159282, 86311, 134105 | 关卡脚本里的「设定倍率」指令（演出/子弹时间），Execute 是可 hook 的执行体 | 流程 | 高 |
| `TimeScaleHandler`（New / Respawn / Equals） | 类+方法 | 4 | 31345, 137938, 137939, 137940 | 叠加式倍率修饰器句柄：多个来源（演出/减速/子弹时间）叠加，Respawn 说明可被反复重建 | 流程 | 中 |
| `get_baseTimeScale` / `AddBaseTimeScale` / `BaseTimeScale` | 字段 | 4 | 61124, 61516, 61517 | 基准倍率，注意它在 **ConstCommonExcel（61106 起）**，不在 ConstCombatExcel | 数值 | 中 |
| `LockByTimeLimit` / `elapsedTimeLimit` / `isTimeLockedByTimeLimit` / `lockedTimeScaleByTimeLimit` | 方法+字段 | TimeLimit 78 | 32699, 32706, 32711, 32712 | 超时锁定：战斗耗时超限后锁住倍率（防拖时间），与风控口径相关 | 流程 | 中 |
| `killUnderTimeScale` / `IgnoreTimeScale` / `DelayIgnoreTimeScalePromise` | 字段+方法 | 1 / 1 / 1 | 21301, 21299, 21377 | 倍率是否影响击杀判定/动画的开关 | 数值 | 中 |
| `BattleTime` | 字段 | 19 | 33393 | **陷阱**：结算 UI 文本字段（邻居 VictoryImg/DefeatImg/RewardPrefab），非战斗时钟 | 只读观察 | 低（勿用） |
| `MX.Logic.Services.TimeService`（ApplyTimeBias / DateTimeToUnixTimestamp / GetLastPeriodDateTime） | 类 | Services 域 240 内 | 129089, 129090 | 墙钟/服务器时间换算（生日邮件、周期刷新），与战斗倍率无关 | 只读观察 | 低（勿用） |
| `KatmaiTimeScaleMultiplicator` / `FxTrailTimeScale` / `GroundCommandBattleTimer` | 类 | 3 / 11 / 4 | 21371, 21300, 86137 | 框架、特效尾迹、UI 计时器，非核心 | 只读观察 | 低 |

**【最佳 hook 点建议】** Dobby inline hook 首选 `TimeScaleService.set_TimeScale` / `ApplyTimeScale`（在 21296 / 21304 有名字、且属高概率真实方法体，可把传入倍率放大并 clamp 掉 `AllowedMaxTimeScale` 的限制）；要「冻结/暂停战斗」则 hook `MX.Logic.Battles.LogicGameTime.Pause` / `Resume`（158695 / 158697，扁平名给出完整类型，解析最稳）。`allowedMaxTimeScale`（60751 / 61069）是 FlatBuffers 配置结构体字段，**只能按名反射读**，不能当函数 hook；而且它只是本地常量，服务端若比对战斗时长，本地加速在结算侧会被发现（见 §3）。

---

## 3 结算与奖励（BattleResult / RewardDB / AddReward / ReceiveReward / FirstClear / RewardPopup / RewardInfo / ClearReward）

<!-- D3 -->

---

## 4 关卡与进度（CampaignStage / Scenario / Mission / StageClear / ContentLog / Chapter / SubStage）

<!-- D4 -->

---

## 5 抽卡（Gacha / GachaResult / GachaInfo / Pickup / GachaDB）

<!-- D5 -->

---

## 6 成长（CharacterData / Equipment / ItemDB / LevelUp / Exp / StatLimit / CharacterDB / EquipmentDB）

<!-- D6 -->

---

## 7 技能 / CD / 费用（SkillCost / EXSkill / CostRegen / CoolTime / SkillUse / SkillDB）

<!-- D7 -->

---

## 8 敌方 / 自动（Enemy / Boss / Raid / Arena / AutoBattle / TacticsAI / TacticEntityType）

<!-- D8 -->

---

## 9 大厅 / UI 对照（MemoryLobby / CharacterVisual / EntityVisual / SpineAnim — 已有 hook，仅作对照）

<!-- D9 -->

---

## 10 跨域结论（一句话版）

<!-- SUMMARY -->
