# 碧蓝档案国服（com.RoamingStar.BlueArchive）逆向调研 · 增量清单

> 调研性质：**只读**。不安装、不启动、不联网、不改 AzusaBA 源码。
> 工作区根 `$WS=/data/user/0/com.ai.assistance.operit/files/workspace/9dc0fd0c-7cad-4366-8d0b-bad7165d8587`
> 全部结论标注证据；拿不到证据的写「未验证」。
> 本文件接续前一轮被 Operit 宿主 OOM 打断的调研（`audit/ba-apk/`、`audit/ba-work/` 内的中间产物直接复用，未重复解包 2.1 GB 的 base.apk）。

---

## 零、现场与方法

### 0.1 复用的现成产物（本轮没有再解包 APK）

| 产物 | 大小 | 用途 |
|---|---|---|
| `$WS/audit/ba-apk/base.apk` | 2,126,400,085 B | 未再复制/解压（磁盘仅剩 6.1 G） |
| `$WS/audit/ba-apk/classes.dex` / `classes2.dex` | 9.3 MB / 10.2 MB | Java 层 |
| `$WS/audit/ba-apk/jadx/sources` | 27 MB / 3255 个 .java | Java 层（已反编译好） |
| `$WS/audit/ba-apk/lib/arm64-v8a/` | 24 个 .so | Native |
| `$WS/audit/ba-apk/lib/arm64-v8a/libil2cpp.so` | 270,927,056 B | IL2CPP 运行时 |
| `$WS/audit/ba-work/x/assets/bin/Data/Managed/Metadata/global-metadata.dat` | 38,426,024 B | 元数据 |
| `$WS/audit/ba-apk/out/strings/libil2cpp.so.txt` | 77,730 行 | 已提取的 so 字符串 |
| `$WS/audit/ba-apk/out/kw-hits.tsv` | 前一轮反作弊关键词 × so 命中矩阵 | 风险章 |
| `$WS/audit/ba-apk/out/metadata-strings.txt` | **本轮新增**，768,396 行 / 10 MB | `strings -n 4 global-metadata.dat`（0.19 s） |

### 0.2 本轮的内存纪律（宿主刚 OOM 崩过一次）

所有大输出一律重定向到文件后 `head -c 4000` / `head -50` 分批取；单条命令输出 ≤ 100 行；不对 38 MB metadata、270 MB libil2cpp.so 做整体打印。`strings` 全量落盘一次后反复 grep，避免重复扫描。

---

## 一、APK / IL2CPP 结构事实

### 1.1 只有 arm64 一个 ABI，Native 层 24 个 so

```
$ ls $WS/audit/ba-apk/lib
arm64-v8a
$ ls $WS/audit/ba-apk/lib/arm64-v8a | wc -l
24
```
→ 无 `armeabi-v7a`、无 `x86`：**纯 64 位包**。任何 hook 代码只需编 arm64。
24 个 so 中含：`libil2cpp.so`(270 MB)、`libunity.so`、`libcrashlytics*`、`libmain.so`、`lib_burst_generated.so`、`libmsaoaidsec.so`(MSA OAID)、`libsigner.so`、`libthemis.so`、`libtprt.so`、`libtapsdkcore.so`(TapSDK)、`libsqlcipher.so`、`libcri_ware_unity.so`(CriWare 音频)。

### 1.2 纯 IL2CPP：包内没有可反编译的托管 DLL

```
$ find $X/assets/bin/Data/Managed -maxdepth 3
.../Managed
.../Managed/Metadata
.../Managed/Metadata/global-metadata.dat
```
`Managed/` 下**只有** `Metadata/global-metadata.dat`，没有任何 `Assembly-CSharp.dll` 之类。
→ 老式的「dnSpy 改 DLL 再回包」路线**在本包不存在**；IL2CPP 逻辑只能从 metadata + libil2cpp.so 走。

### 1.3 libil2cpp.so 的 il2cpp_* 导出齐全（这是本项目最重要的事实）

```
$ grep -o 'il2cpp_[a-z_]*' out/strings/libil2cpp.so.txt | sort -u | wc -l
237
$ for a in il2cpp_class_from_name il2cpp_class_get_method_from_name il2cpp_domain_get \
           il2cpp_domain_assembly_open il2cpp_field_get_offset il2cpp_string_new il2cpp_thread_attach
  do grep -cx $a out/strings/libil2cpp.so.txt; done
1 1 1 1 1 1 1     ← 7 个关键 API 全部命中
```
→ 运行时可拿到完整 IL2CPP 反射 API：**按「程序集名 + 命名空间 + 类名 + 方法名」在内存里解析出函数指针**，不需要静态知道偏移。AzusaBA 现有实现（`main.cpp:443 GetMethodInfo(dll,ns,cls,meth,argc)`、`main.cpp:1578 FindClassByFingerprint`）就是这条路线，已在 3.0.2 上跑通，是本轮所有新增功能的落地前提。

### 1.4 global-metadata.dat 是否加密：**头部不是标准 IL2CPP 头，但名字表是明文**

证据链（全部可复现）：

```
$ xxd -l 32 global-metadata.dat
00000000: 9443 7212 184b 9eec 6667 6666 a662 6566  .Cr..K..fgff.bef
00000010: a663 6566 6ea2 6d66 aeaf 6866 ee1a 0a66  .cefn.mf..hf...f

$ grep -abo $'\xaf\x1b\xb1\xfa' global-metadata.dat | head
（无输出）

$ strings -n 4 global-metadata.dat | wc -l
768396
```

标准 IL2CPP metadata（v24~v31 全部）第 0 个字段是 sanity `0xFAB11BAF`（小端 `AF 1B B1 FA`），第 1 个字段是版本号（如 `0x1F` = 31）。实测：magic = `0x12724394`（非标准），紧随的 4 字节 = `0xEC9E4B18`（不可能是一个版本号）；全文件 grep 也搜不到标准 magic 出现。
→ **头部被改写/被加密，不能按标准布局直接读 import 偏移表**。

但同一文件里名字与字面量是**明文**：

```
$ strings -t d -n 4 global-metadata.dat | grep -E ' (EntityVisual|BattleEntity|AttackPower|MaxHP)$'
1111786 EntityVisual
1111871 BattleEntity
1286035 AttackPower
1286060 MaxHP
```

而且明文不是集中在某个 section，而是**遍布整个 38 MB**（`strings -t d` 按 1 MB 分桶，每桶条数）：

```
0MB:15743 1MB:40191 2MB:36769 3MB:34756 4MB:20666 5MB:19222 6MB:42767 7MB:32141
8MB:14366 9MB:12137 10MB:12323 11MB:12759 12MB:13709 13MB:14750 14MB:12764
15MB:11403 16MB:10332 17MB:8677 18MB:6284 19MB:10746 20MB:9093 21MB:9949
22MB:9603 23MB:4640 24MB:11075 25MB:7946 26MB:12461 27MB:7259 28MB:6757
29MB:6615 30MB:6017 31MB:7619 32MB:6122 33MB:5096 34MB:24687 35MB:17845 36MB:8571
```
（0 MB 桶就有 15,743 条 → 连文件开头附近都有大量明文，与「整文件加密」不相容。）

**结论（定性）**：`global-metadata.dat` 属于「**头部/结构表被改写或自定义 magic，名字与字面量表保持明文**」这一类，**不是整文件加密**。工程后果：
1. 静态 `Il2CppDumper` 直接吃这个文件大概率失败（需先还原头部，细则见 §三.1）；
2. 但静态 `strings` 已经足够回答「某个类/方法名在这个版本里存在吗」这类问题 —— 本节所有命名结论都建立在这上面；
3. 真正定位函数仍走 §1.3 的运行时按名解析，或者对运行时内存里的 metadata dump。

### 1.5 明文命中样本：能用来判断可 hook 目标是否真实存在

命名必须是**子串**匹配（`grep -c`，不能用 `grep -x`）——metadata 的短名字在文件里常常紧邻排列，`strings` 会把它们连成一行。

```
$ S=out/metadata-strings.txt
$ for n in BattleResult CampaignStage Gacha RewardDB AddReward ReceiveReward ApplyDamage \
           CalcDamage set_TimeScale GetSkillCost OnDead CostRegen EXSkill MemoryLobbyData \
           AccountDB SceneManager TimeScale AntiCheat CheatDetect; do echo $n=$(grep -c $n $S); done
BattleResult=83   CampaignStage=300  Gacha=1644        RewardDB=34      AddReward=173
ReceiveReward=89  ApplyDamage=21     CalcDamage=5      set_TimeScale=2  GetSkillCost=5
OnDead=5          CostRegen=44       EXSkill=40        MemoryLobbyData=6 AccountDB=8
SceneManager=27   TimeScale=93       AntiCheat=0       CheatDetect=0
```

`BlueArchive.dll` / `BlueArchive.FirstPass.dll` 也在串表里（`grep -c BlueArchive` = 6），与现有模块 `GetMethodInfo("BlueArchive.dll", ...)` 的用法一致。

注意 `AntiCheat=0` / `CheatDetect=0`：**托管层没有叫这两个名字的东西** → 反作弊不在 C# 侧，检测在 native/Java（见 §五 与反作弊专项）。

### 1.6 未验证项（明确标出，不猜）

- `assets/aa/catalog.json` 是否真为 81 MB：`zip_listing.txt` 只记路径不记大小，本轮未解压该文件 → **未验证**。`$WS/audit/ba-work/x/assets/aa/` 里只有 `settings.json`(3161 B)，catalog.json 并未落盘。
- metadata 头部的加密算法/密钥来源 → **未验证**（只在 §三.1 给出可验证的判定路径）。
- Unity 引擎精确版本号：so 串里没抓到 `20xx.y.zf1` 形态的版本串 → **未验证**。

---

## 一·五、现有模块 AzusaBA 的能力边界（增量清单的起点）

> 这一节是本轮新增的「基线盘点」，用来回答「哪些功能已经有了、新增的不要重复做」。

### 1.5.1 UI 上已存在的开关（14 个，`main.cpp` 里 `ToggleSwitch("...")` 全量）

```
自动旋转 / 自定义大小 / 人物倒立 / 自定义等级 / 下雨特效 / 下雪特效
解锁所有记忆大厅 / 替换大厅角色 / 全局替换（所有大厅角色 → 目标）
伤害倍率 / 锁血（我方伤害归零）/ 人物移速 / 人物射程 / 枪械射速
```

### 1.5.2 Native 侧已安装的 hook（`main.cpp` 里出现的 27 个 `old_*` 函数指针）

战斗只有 2 个：`old_ApplyDamage`、`old_get_CurrentStat`。
其余 25 个全部是大厅/外观/等级显示：`EntityVisualAwake/Start`、`CharacterVisualLateUpdate`、`SpineAnimLateUpdate`、`SpineBaseAwake/OnEnable`、`CreateLobbySpineLoadInfo`、`LoadPortraitSpine`、`GetListByCharacterId`、`HasDataByCharacterId`、`MemoryLobbyData_InitializeCommon`、`CharacterData_InitializeCommon`、`TryGetMemoryLobbyExcelByIndex`、`LobbySpineCount`、`MemorialLobbySpineCount`、`IsMemorial`、`SameCharacterAndCostume`、`CanRotateLobbySpine`、`RefrehsLevelExp`、`SetLevelExp`、`UIAccOnOpened/RefreshAll/RefreshFav`、`UIAccountInfoRefreshLv` 等。

→ **能力边界一句话**：现有战斗类功能 = 「改我方 stat 表 + 我方受击伤害归零」这 2 条通道，覆盖 5 个数值维度；**掉落、奖励结算、关卡、体力、暴击/闪避、技能 CD、时间缩放、敌人削弱、自动战斗全部空白**。

### 1.5.3 战斗功能的确切实现机制（新增功能应复用这条通道）

`get_CurrentStat_Hook`（`main.cpp:1549`）→ `ApplyStatMods`（`main.cpp:1479`）的结构：

```
stat + 0x28 → valueTable
valueTable + 0x18 → entries 指针
valueTable + 0x20 → count（int，代码里限 ≤512 做防御）
entry = entries + 0x20 + i*24
  entry + 0   → int32 是否空槽（<0 = 空）
  entry + 8   → int32 key（Stat 参数枚举）
  entry +16   → int64 value
```

当前改写的 key（`switch(key)`，`main.cpp:1503-1531`）：

| key | 语义（代码注释） | 行为 |
|---|---|---|
| 13 | MoveSpeed 移速 | × `moveSpeedMultiplier` |
| 21 / 14 | WeaponRange 射程 / SightRange 视野 | × `attackRangeMultiplier` |
| 38 / 2 | DamageRatio 伤害倍率 / AttackPower 攻击力 | × `damageMultiplier` |
| 39 | DamagedRatio 受击倍率 | 置 0 = 锁血 |
| 34 / 20 | NormalAttackSpeed 枪械射速 / IgnoreDelayCount | × `fireRateMultiplier` / 直接写 9999 |

并且**只改我方**：`isPlayer = (GetTacticEntityType(instance) == TT_Student)`（`main.cpp:1564`），敌人保持原样。
原始值有「原值缓存 + 撤销」机制（`StatGetOrig` / `StatWriteOrigForKey` / `StatRestoreRecent`），功能关闭时把最近动过的 stat 写回原值。

`ApplyDamage_Hook`（`main.cpp:1314`）只做一件事：我方（`IsPlayerSide`）受击时把 `damageResult+0x18` 的 int64 写 0（锁血）。
注释明确写着**这里不再乘倍率**：`ApplyStatMods` 已经乘过 AttackPower(2)/DamageRatio(38)，再乘一次会变成 mult²（开 10 倍实际 100 倍），倍率只保留属性表这一条通道（`main.cpp:1349-1351`，P0-6 修复）。

**这两条经验对新增功能的直接价值**：
- 任何「改我方数值」的新功能 → 只需在 `ApplyStatMods` 的 switch 里加新 key，无需新 hook 点、无需新反射调用，风险最低；
- 任何「改结算/改伤害流向」的新功能 → 挂在 `ApplyDamage_Hook` 上，但注意结算期实体正在销毁，`main.cpp:1324-1328` 的全关透传与 `IsValidManagedPtr` 校验是防崩红线，不能省。

### 1.5.4 Hook 与注入机制（决定了新增功能的挂载方式）

- Hook 引擎：**DobbyHook**（`main.cpp:1698 InstallHook()` 直接调 `DobbyHook`）。
- **不要用 `Anti/MemoryHide.h`、`Anti/SeccompHook.h`**：`main.cpp:1695-1697` 有实测结论——那套会 inline hook libc 的 `openat/prctl/dladdr/sigaction` 并用 `mremap` 把已加载可执行页换成诱饵页，多线程下直接 SIGSEGV（崩在 GLThread/UnityMain，pc 落匿名映射），**当前构建已明确剥离**，只保留 Dobby。新增功能不要把它们加回来。
- 单实例保护：环境变量 `AZUSA_NEKO_HOOKED`（`MarkThisProcessHooked`），防止同一进程载入两份 payload 导致同一函数被 hook 两遍。
- 符号完整性前置检查：il2cpp 关键符号缺一个就整体放弃装 hook（宁可不生效也不装在 null 上）。
- 注入路径：Java 侧 `HookLoad.java` 通过 Xposed 在目标进程调 `System.load(payload)`/`System.loadLibrary(Neko)`（`HookLoad.java:494-504`），`GLES3JNIView` 替换 Unity 的 GLSurfaceView 以叠加 ImGui 图层；音量键 UI 开关挂在 `android.app.Activity#dispatchKeyEvent`（`HookLoad.java:284`）。
- 配置持久化：`Game/Config.cpp` 纯文本 `key=value`，带 `version`（当前 `kCfgVersion=9`）；**新增字段必须同时改 `Config.h` 结构与 `Config.cpp` 的 key 表并把 version +1**，否则旧配置文件会被改名备份、用户设置全丢。

---

## 三、Native 可 hook 点表

> 作者：recon-hooks（team）。本节**全部为静态只读证据**，未上机、未安装、未联网。
> 证据路径缩写：`M:` = `$WS/audit/ba-apk/out/metadata-strings.txt`（768,396 行，行号即证据）；`CPP:` = `$WS/AzusaBA/app/src/main/jni/main.cpp`。

### 3.0 本轮新增的取证工具：metadata 里有成片的 `MX-<域>-<类>-<方法>0` 串

这是本轮最有用的发现——它等于把 C# 的「命名空间 + 类名 + 方法名」三元组摊平写进了明文：

```
$ grep -n '^MX-Logic-Battles-DamageCalculator-' M
132101 IsHit   132117 CalcCriticalChance   132118 IsCritical   132121 DamageReductionRate
132122 CalcApplyDamageRatio   132123 CalcDamage
$ grep -n '^MX-Logic-BattleEntities-BattleEntity-' M | head
133545 CacheInitialStat  133547 CanBeTargeted  133548 TryGetValueStat  133550 TryGetRateStat
133562 GetStatOfPhase  133568 Move  133573 OnDamaged  133575 ApplyStat  133577 SetUntargetableException
```

用法澄清（避免误用）：`MX-...-CalcDamage0` **本身不是 metadata 里的方法名**，它只是「全限定名映射表」；实际解析仍用 plain 名（`CalcDamage` @ `M:69913`）走 §1.3 的 `GetMethodInfo("BlueArchive.dll","MX.Logic.Battles","DamageCalculator","CalcDamage",n)`。
**价值**：不用再猜类归属，也不用静态解 metadata 头（§1.4 已证明头部被改写）。

### 3.1 前置事实（决定了 hook 的挂法，必须先看）

1. `ApplyDamage` / `get_CurrentStat` 在 `BattleEntity` 上是 **abstract（无函数体）**，必须用属性指纹定位具体实现类 `Character`：`CPP:1327-1328` 注释 + `CPP:1340-1357`（`beProps={"HitPoint","MaxHPCapGauge"}`、`charProps={"WeaponSetting","CostumeSetting","GearSetting"}`）。
2. 同名方法唯一无法保证 → 新 hook 点一律要 `(类, 方法名, 参数个数)` 三元组，且优先选**已在 metadata 里能查到唯一类归属**的（下表已给）。
3. 战斗线程与 UnityMain 并发（`CPP:1304` 实测过无锁 `std::map` 并发 insert 崩），**新 hook 里禁止无锁写共享容器**。
4. 结算期实体正在销毁：`CPP:1277-1281` 的全关透传 + `IsValidManagedPtr` 是红线。

### 3.2 可 hook 点表（16 条，按「收益/风险比」排序）

| # | 目标类/方法（程序集=`BlueArchive.dll`） | 证据来源 | 用途 | 实现层 | 难度 | 风险 |
|---|---|---|---|---|---|---|
| 1 | `MX.Logic.BattleEntities.BattleEntity.get_CurrentStat()` | `CPP:1311,1318,1347`（已装）+ `M:36543` `get_CurrentStat` | 全属性读写主通道；现有 5 维功能全在此 | **stat 表偏移** `stat+0x28→+0x18/+0x20`，`entry=entries+0x20+i*24` | 低（已跑通） | 低（纯本地） |
| 2 | `BattleEntity.ApplyStat(...)` | `M:133575` | buff/装备重算后的**最终落点**；补 `get_CurrentStat` 覆盖不到的路径 | Dobby | 中（需定参数个数） | 中（高频+重入） |
| 3 | `BattleEntity.TryGetValueStat(...)` / `TryGetRateStat` | `M:133548` / `M:133550` | 只读校验：dump 真实 stat 值，用来标定 key 枚举 | 反射调用（不 hook） | 低 | 低（只读） |
| 4 | `BattleEntity.GetStatOfPhase(...)` | `M:133562` | 分阶段（多血条/Phase）取值，UI 数值同步 | Dobby | 中 | 低 |
| 5 | `BattleEntity.OnDamaged(...)` | `M:133573` | 敌方受击后处理：秒杀/伤害转真伤/击杀链 | Dobby | 中 | 中（结算期销毁） |
| 6 | `MX.Logic.Battles.DamageCalculator.CalcDamage(...)` | `M:132123`（+`M:69913` plain 名） | 伤害总公式**唯一乘子点**，天然避免 `mult²`（对比 §1.5.3 的双通道坑） | Dobby | 中（结构体返回值） | 中 |
| 7 | `DamageCalculator.CalcCriticalChance` / `IsCritical` | `M:132117` / `M:132118` | 必暴击 / 暴击伤害 | Dobby | 中 | 中（.NET 内部高频） |
| 8 | `DamageCalculator.IsHit(...)` | `M:132101` | 必中 / 我方闪避 | Dobby | 中 | 中 |
| 9 | `DamageCalculator.DamageReductionRate(...)` | `M:132121` | 我方减伤 / 敌方增伤（比锁血更自然） | Dobby | 中 | 中 |
| 10 | `BattleEntity.CanBeTargeted(...)` / `SetUntargetableException` | `M:133547` / `M:133577` | 我方免锁定（比锁血更彻底）；也可反向给敌 | Dobby | 低 | 中（AI 索敌退化→卡关） |
| 11 | `MX.Logic.BattleEntities.Character.OnDied` / `OnDying` | `M:138467` / `M:138469` | 敌方即死 / 我方免死 | Dobby | 中 | 中（即死会跳过掉落/演出流程） |
| 12 | `Character.OnAmmoReloaded` / `OnBulletCountChanged` | `M:138461` / `M:138462` | 无限弹药 / 不换弹 | Dobby | 低 | 低 |
| 13 | `MX.Logic.Battles.CarrierSkillCard.ForceCoolTimeSet` / `ForceStartRecharging` / `ChargeComplete` / `CanUseSkill` / `UseSkill` | `M:133888` / `133887` / `133889` / `133898` / `133899` | EX 费用与冷却清零 | Dobby | 中 | 中（`Battle.OnPlayerSkillCardCostAdded` @`M:134061` 会记录费用事件） |
| 14 | `PlayerSkillCardManager.SetAutoUse` + `SkillCard.AutoUseCard` + `SkillCardService.CanUseAutoSkillCard` | `M:133890` / `M:134039` / `M:134033` | 全自动放技能 | **反射改状态位（无需 hook）** | 低 | 中（操作频率可统计） |
| 15 | `TimeScaleService.set_TimeScale` / `get_TimeScale` + `GroundCommandSetTimeScale.Execute` | `M:31333` / `31330`（类 `M:31329`）/ `M:159279` | 战斗加速 / 子弹时间 | Dobby | 低 | **高**（见 §3.3） |
| 16 | `Battle.EndBattle` + `CampaignService.CalcStarCount` / `IsClearTimeInSec` / `CalcTacticRank` | `M:134078` / `129706` / `129709` / `129711` | 本地三星/评级 | Dobby | 中 | **高**（服务端复算） |

补充（用来做「观测/风控自检」，**不要改写**）：`ExcessiveTouchCheck-StartCheck/StopCheck` `M:23388/23389` + `Battle.WriteExcessiveTouchSummary` `M:132821` + `CheatService.DoSomething` `M:156861` + `CheatCodeData.InitializeClient` `M:161634`；违规枚举目前只见到 `Violation_Default` / `Violation_ExcessiveTouch`（`M:77167-77168`）。**改写这些等于主动往上报链路里写脏数据**，风险极高。

Java 层唯一可用的 hook 面仍是生命周期/输入：`com.tech.sdk.bridge.TechSDKUnityPlayerActivity#onResume/onStop`（它只重写 4 个方法）、父类 `UnityPlayerActivity#dispatchKeyEvent`（见 `audit/ba-java.md` §2）。**Java 层没有任何战斗逻辑**，别在那里找。

### 3.3 风控口径（决定「加速类」功能风险高）

| 字段 | 证据 | 归属 | 后果 |
|---|---|---|---|
| `AllowedMaxTimeScale` | `M:60752`（+`get_` @`M:60875` 一带，详见 `audit/ba-il2cpp.md` §三） | `ConstCombatExcel`（FlatBuffers 主数据表） | 时间倍率上限，**消费者未验证** |
| `MinimumClearTime` / `ArenaMinimumClearTime` | `M:60740,60743,60744,60745,60746` | 同上 | 清关时长下限 |
| `CheckCheaterMaxUseCost{NonArena,Arena,MultiFloorRaid}` | `M:60748,60750,60807` | 同上 | 消耗类上限 |
| `ExcessiveTouchCheckTime/Count` | `M:23378,23379,23380,23381` | 同上 | 触点频率 |
| 结果上传 | `CampaignSubStageResultNetworkTask` `M:29363`；`AccountReportXignCodeCheater*` `M:29214-29218` | 网络层 | 清关时长/结果**走服务端**，且存在 XignCode 上报通道 |

→ 结论：**改本地数值 > 改时间/改结果**。凡影响「时长 / 消耗 / 星级」的功能，都落在服务端可见面上。

---

## 四、Top10 功能（实现层优先 stat 表加 key）

> 排序 = 交付优先级（收益/风险比）。凡写「stat key」的，前提是**运行时先 dump `Stat` 枚举确认真实 key 值**：目前只有 13/21/14/38/2/39/34/20 这 8 个经 `CPP:1503-1531` 实测确认，其余（如 `CriticalRate` @`M:89896`）只证明名字存在，**枚举值未验证**。

| # | 功能 | 实现层（优先 stat key） | hook 点 | UI 开关（ImGui，沿用 `ToggleSwitch`/滑条） | 服务端校验风险 |
|---|---|---|---|---|---|
| 1 | 敌方全体削弱 | **stat key**：复用 `ApplyStatMods`，把 `isPlayer` 分支改成「按 side 选倍率」，敌方 key 38/2/39 反乘 | `get_CurrentStat`（已装，**零新增 hook**） | 「敌人削弱」滑条 0.05–1.00 | 低（纯本地；星级只看时间/存活） |
| 2 | 我方无敌（扩展锁血） | 现有 key 39 已够；补 `ApplyDamage_Hook` 的 `IsPlayerSide` 分支覆盖召唤物 | `ApplyDamage`（已装） | 「无敌」开关（替代/合并现「锁血」） | 低 |
| 3 | 暴击锁定 | stat key（`CriticalRate`/`AddCriticalDamageRate` `M:89896-89899`，**值待 dump**）；无对应 key 时退到 hook | `CalcCriticalChance` / `IsCritical` `M:132117-132118` | 「必暴击」开关 + 倍率 | 低–中（伤害分布异常可统计） |
| 4 | EX 连发（费用/冷却清零） | stat 表无 Cost 维度 → **必须方法 hook** | `CarrierSkillCard.CanUseSkill/UseSkill/ForceCoolTimeSet` `M:133898/133899/133888` | 「EX 消耗倍率」滑条 + 「无冷却」开关 | 中（`OnPlayerSkillCardCostAdded` 事件留痕） |
| 5 | 全自动放技能 | **反射改状态位，不用 hook** | `PlayerSkillCardManager.SetAutoUse(true)` `M:133890` → `SkillCard.AutoUseCard` `M:134039` | 「自动放技能」开关 | 中（操作时间线可被统计） |
| 6 | 战斗加速（1–8×） | 非 stat 维度 | `TimeScaleService.set_TimeScale` `M:31333`（或在 `Battle.Update` `M:134079` 前置乘） | 「战斗速度」滑条 1.0–8.0× | **高**（`AllowedMaxTimeScale` + `MinimumClearTime` + 结果上传 `M:29363`） |
| 7 | 无限弹药 / 不换弹 | stat key 34/20 已有近似；真解需 hook | `Character.OnAmmoReloaded` / `OnBulletCountChanged` `M:138461/138462` | 「无限弹药」开关 | 低 |
| 8 | 必三星 / 评级 | 非 stat 维度（改结果计算） | `CampaignService.CalcStarCount` / `CalcTacticRank` `M:129706/129711` | 「必三星」开关 | **高**（服务端按 `M:29363` 复算） |
| 9 | 秒杀（点敌即死） | 直接写敌方 HP stat 到 0（走 stat 通道）或 hook 死亡入口 | `Character.OnDied/OnDying` `M:138467/138469`（或 `OnDamaged` `M:133573`） | 「秒杀」开关（长按/点击选择） | 中–高（通关时长趋 0，直接命中 `MinimumClearTime`） |
| 10 | 免锁定 / 站位自由 | 非 stat 维度 | `BattleEntity.CanBeTargeted` `M:133547` + `SetUntargetableException` `M:133577` | 「无敌仇恨清零」开关 | 中（位置/索敌异常，服务端是否校验未验证） |

**交付建议顺序**：1 → 2 → 7 → 5 → 3 → 4 → 9 → 10；6 与 8 **放在实验开关之后**（它们是唯二直接进服务端可见面的）。
**每项落地必带的样板**：`Config.h`/`Config.cpp` 加字段 + `kCfgVersion` +1（§1.5.4）；关闭时走「原值缓存 + 撤销」（`StatGetOrig`/`StatWriteOrigForKey`/`StatRestoreRecent`）；开关全关时**首行透传**（`CPP:1277-1281` 既有写法）。

---

## 五、不可行方向（每条给理由）

| # | 方向 | 为什么不可行（证据） |
|---|---|---|
| 1 | 静态改托管 DLL 再回包（dnSpy/ILSpy） | `Managed/` 下只有 `Metadata/global-metadata.dat`，**无 `Assembly-CSharp.dll`**（§1.2）。路线在本包不存在 |
| 2 | Il2CppDumper 静态出偏移表 | metadata 头 magic=`0x12724394`、version=`0xEC9E4B18`、第 3 个 u32 越界，全文件标准 sanity `AF 1B B1 FA` 命中 0（§1.4 / `audit/ba-il2cpp.md` §一）。**要静态 dump 必须先逆头部加密，收益不抵成本** |
| 3 | `dlsym`/`xdl_sym` 按名取 `il2cpp_*` | `DT_HASH` 2647 个符号里 `il2cpp_*` = **0**；245 处名字中 241 处在 `.dynstr` 内成簇但**不被任何 dynsym 项引用**（`ba-il2cpp.md` §二）。⚠️ 与 §1.3「strings 有名字」不矛盾但**必须标冲突**：若线上包与本 APK 一致，AzusaBA 的 `Il2CppApiReady()` 会失败 → 只能硬编码偏移/特征码（版本一升即废）。**此项须真机 logcat 复验，属本轮最大未验证风险** |
| 4 | 改客户端常量把风控关掉（`AllowedMaxTimeScale`/`MinimumClearTime`/`CheckCheaterMaxUseCost*`） | 这些是 `ConstCombatExcel` 的 **FlatBuffers 表字段**（`M:60625-61100`），不是编译期常量；改本地只影响本地判定，服务端另有判定（未验证），且时长/结果经 `CampaignSubStageResultNetworkTask`（`M:29363`）上行 |
| 5 | 本地改掉落/奖励/抽卡结果 | 到账真源是服务端响应；本地只有 `AddReward`（`M:38605`）、`RewardParcel`（`M:38604`）、`GroundModuleRewardExcel.get_DropItemModelPrefabPath`（`M:161973`，纯表现资源路径）。本地改 = 造出「UI 有、背包没有」 |
| 6 | 本地改体力/货币/钻石 | `AccountCurrencySyncRequest/Response`（`M:72568-72569`）双向同步，本地写值会被服务端快照覆盖；且属封号高危 |
| 7 | 改 Java 层战斗逻辑 | Java 层零战斗代码：主 Activity 只重写 `onDestroy/onResume/onStop`（`audit/ba-java.md` §2），战斗全在 `libil2cpp.so` |
| 8 | 恢复 `Anti/MemoryHide.h` / `SeccompHook.h` 那套 inline hook libc 的隐匿方案 | 已实测多线程 SIGSEGV（`CPP:1695-1697`），当前构建明确剥离。**不要加回来** |
| 9 | 对抗 ACE / AirSDK 模拟器检测 / 数美 / Turing 风控 | Java 层是独立加固+风控体系（`com.ace.gshell` 4 类、`com.airi.*` 914 类、ishumei 193、turingfd 201，`ba-java.md` §1）；静态无指令流分析（执行路径未验证）。对抗成本 ≫ 收益，且属主动对抗风控 |
| 10 | 伪造/抑制 `AccountReportXignCodeCheater` 上报 | 该通道是客户端→服务端单向（`M:29214-29218`）。伪造或静默等于**主动自曝**；同理不要碰 `ExcessiveTouchCheck` / `CheatService.DoSomething` 的返回值 |
| 11 | 只在 ImGui 层伪造数值显示 | 数值真源在 stat 表，UI 只读；伪造会与战斗结算不一致。现有锁血/伤害倍率都已在真源实现，说明这条路早被证否 |

**本轮未验证清单（不猜）**：Il2CppDumper 实跑；真机 `xdl_sym` 是否失败；`AllowedMaxTimeScale`/`MinimumClearTime` 的**实际消费者**与默认值；`Stat` 枚举除上述 8 个 key 外的取值；服务端对清关时长/星级是否复算；`DamageCalculator.CalcDamage` 的真实参数与返回值形态（结构体 or 指针）。
