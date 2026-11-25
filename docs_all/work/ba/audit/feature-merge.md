# AzusaBA 5.2.6 功能合并（feature-merge）

> 作者：recon-hooks。本文件先写「现状清单」，再写逐项实现与验证。
> 代码基线：`$WS/AzusaBA/app/src/main/jni/main.cpp`（4,899 行，216,491 B，mtime 11-11 15:33）。

## 一、现状清单（改前取证，2026-11-11 18:2x）

### 1.1 现有 14 个 ImGui 开关（`ToggleSwitch(...)`）

| # | 标签 | Config 字段 | 所在页 |
|---|---|---|---|
| 1 | 解锁所有记忆大厅 | `memoryLobby.unlockAllMemoryLobby` | 主要功能 |
| 2 | 替换大厅角色 | `memoryLobby.replaceCharacter` | 主要功能 |
| 3 | 伤害倍率（+ SliderInt 1–1000） | `battle.enableDamageMult` / `damageMultiplier` | 主要功能 |
| 4 | 锁血（我方伤害归零） | `battle.enableGodMode` | 主要功能 |
| 5 | 人物移速（+ 1–20） | `battle.enableMoveSpeed` / `moveSpeedMultiplier` | 主要功能 |
| 6 | 人物射程（+ 1–20） | `battle.enableAttackRange` / `attackRangeMultiplier` | 主要功能 |
| 7 | 枪械射速（+ 1–50） | `battle.enableFireRate` / `fireRateMultiplier` | 主要功能 |
| 8 | 全局替换（所有大厅角色 → 目标） | `memoryLobby.globalReplace` | 主要功能 |
| 9 | 自定义等级（+ 1–90） | `localLevel.enable` / `level` | 程序设置 |
| 10 | 下雨特效 | `ui.enableRain` | 程序设置 |
| 11 | 下雪特效 | `ui.enableSnow` | 程序设置 |
| 12 | 自动旋转（+ 10–360°/s） | `lobbyLook.autoRotate` / `rotateSpeedDeg` | 程序设置 |
| 13 | 自定义大小（+ 30–300%） | `lobbyLook.customScale` / `scalePercent` | 程序设置 |
| 14 | 人物倒立 | `lobbyLook.upsideDown` | 程序设置 |

另有 `ui.fontScalePercent`（字号滑条，非开关）。

### 1.2 现有 27 个 `old_*` 函数指针 / 26 个已装 hook（idx 0–26，H16 已删除）

战斗只有 2 个：`old_ApplyDamage`(idx11)、`old_get_CurrentStat`(idx12)；其余 24 个全是大厅/外观/等级显示。
`HookTrace` 的 `seen[32]` 与 `g_hookMask & (1u<<idx)` 决定了 **idx 必须 ≤31**（本轮新增全部落在 27–31）。

### 1.3 现有战斗数值通道（本轮复用，不改默认行为）

- `get_CurrentStat_Hook` → `ApplyStatMods(stat, isPlayer)`：只改我方（`type == TT_Student`）。
- 已实测 8 个 stat key：`13` MoveSpeed / `21`+`14` WeaponRange+SightRange / `38`+`2` DamageRatio+AttackPower / `39` DamagedRatio(锁血) / `34` NormalAttackSpeed / `20` IgnoreDelayCount。
- 原值缓存：`StatGetOrig`（4096 槽开放寻址 + 自旋锁）、`StatWriteOrigForKey`、`StatRestoreRecent`；关闭时由 `MainThreadTicks`（`SpineAnim_LateUpdate_Hook` 内）还原最近 5 s 动过的 stat。
- 全关透传：`AnyBattleFeatureOn()`（`main.cpp:1543`）为 false 时 `get_CurrentStat_Hook` 直接 return；`ApplyDamage_Hook` 在 `!wantDmg && !wantGod` 时首行 `return old_ApplyDamage(...)`（`main.cpp:1326`）。新增功能必须继续满足这两条。
- 结算期实体销毁：`IsValidManagedPtr` 校验 + 全关透传是防崩红线。

### 1.4 配置持久化

`Game/Config.h`（`struct sConfig`，`int version = 9`）+ `Game/Config.cpp`（`kCfgVersion = 9`，纯文本 `key=value`，仅 int 解析 `CfgToI`）。
保存由渲染线程按「Config 指纹变化 + 800 ms 去抖」自动触发（`save_config(g_cfgPath)`），新增字段无需额外接线。
**任何字段增删 → `Config.h` 的 `version` 与 `Config.cpp` 的 `kCfgVersion` 必须同时 +1（本轮 9 → 10）**，否则旧文件会被改名备份、用户设置全丢。

### 1.5 本轮新增项（8 项，`kCfgVersion` 9 → 10）

| # | 功能 | 实现层 | UI 标签 | 状态 |
|---|---|---|---|---|
| 1 | 敌方全体削弱 | 复用 `ApplyStatMods`（按 side 选倍率），零新增 hook | 「敌人削弱」+ 滑条 0.05–1.00 | 实现 |
| 2 | 我方无敌 | 扩展 `get_CurrentStat_Hook` 的 side 判定（`IsPlayerSide` + 运行时 side 字段校准），`ApplyDamage_Hook` 已用 `IsPlayerSide` | 「我方无敌（含召唤物）」 | 实现（side 校准需实机日志确认） |
| 3 | 无限弹药 | hook `Character.OnAmmoReloaded` / `OnBulletCountChanged` + 运行时字段扫描 | 「无限弹药」 | 实现（字段名启发式，待实机验证） |
| 4 | 全自动放技能 | 反射调 `PlayerSkillCardManager.SetAutoUse(true)`（hook 其 `Update` 拿实例） | 「自动放技能」 | 实现（方法名未命中则自动降级为不生效并打日志） |
| 5 | 暴击锁定 | 优先 stat key `CriticalRate`（**运行时 dump StatType 枚举取真实 key**），同时装 `DamageCalculator.CalcCriticalChance` 按返回类型分派的 hook | 「暴击锁定（待验证）」 | 实现，标注待验证 |
| 6 | EX 无冷却 | hook `CarrierSkillCard.CanUseSkill`（返回 true）/ `ForceCoolTimeSet`（传 0） | 「EX 无冷却」 | 实现；**费用倍率无 stat 维度且改 `OnPlayerSkillCardCostAdded` 等于伪造风控上报 → 不做** |
| 7 | 秒杀敌人 | stat 通道：敌方 `MaxHP(1)=1`、`DamagedRatio(39)` 放大 1000× | 「秒杀敌人（待验证）」 | 实现，标注待验证 |
| 8 | 我方免锁定 | hook `BattleEntity.CanBeTargeted`（我方返回 false） | 「我方免锁定」 | 实现 |

**明确不做**：恢复 `Anti/MemoryHide.h`、`Anti/SeccompHook.h`（实测 SIGSEGV）、加回 `XposedBridge.log`、战斗加速/必三星（直接进服务端可见面，且本轮不在交付清单）。

## 二、实现记录

（下面按落地顺序追加：每项写「文件/函数/行位 → 行为 → 关闭/透传路径」。）

## 三、lead 补丁（输入频率检测绕过 + 已实现项 UI）

时间：2026-11-11 18:5x；产物：`dist/AzusaBA_5.2.6_release.apk`

1. **新增 `battle.bypassExcessiveTouch`（绕过输入频率检测）**
   - 依据：metadata 定位到 `ExcessiveTouchCheck`（MonoBehaviour）结构：`StartCheck/StopCheck/CoCheck` + `checkExpireDuration/checkTouchCount` + `inputTimeList/inputFrameList` + `ExcessiveTouch(bool)`
   - 实现：按指纹 `{"checkTouchCount","inputTimeList","checkExpireDuration"}` 找类，`InstallHook` 掉 `StartCheck`（不启动检测协程）
   - 纯本地，不发任何网络请求；`Config.h/.cpp` 加字段，`kCfgVersion 9→11`
2. **补齐已实现功能的 UI**：敌人削弱（含敌方伤害%滑条 5–100）、秒杀敌人
3. 构建链修正（aarch64 主机）：
   - NDK r27 无 `libgcc`/`libunwind` → 用系统 clang + `-rtlib=compiler-rt` + 自写 `unwind_stub.c`（`-fno-exceptions` 下永不调用）
   - `--gc-sections` 会删掉 `init`，必须配 `-Wl,-u,init -u resize -u step`
   - box64 驱动 NDK clang 链接会 `free(): invalid next size` 崩溃，不可用
4. 产物：3,714,665 B / SHA-256 96b881727a1c28a882bebc84f1f10cd352b03926b4d12f33d0d0e67a8cdb4cc8 / versionCode 2 / versionName 5.2.6 / 证书指纹 354d84da…906d1（未变）
