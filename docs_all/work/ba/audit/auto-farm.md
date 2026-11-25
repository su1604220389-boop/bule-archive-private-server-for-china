# 新号一键起步（AutoFarm v13）交付说明

> 作者：task-farmer ｜ 写域：`Game/Config.h`、`Game/Config.cpp`、`main.cpp`（仅新增段 + 3 处插入点）
> 未触碰 `auto-story` 的 `Config.autoBattle` 与「自动刷 / 自动刷 B」段。

## 1. 结论先说清楚

| 能力 | 状态 | 说明 |
|---|---|---|
| 跳过新手引导 | ✅ 已实现（客户端旁路） | hook `MX.Data.TutorialNewData.GetCompulsoryTutorialList`，逐条打印 tutorialId 后用游戏自己的 `List.Clear()` 清空。**不改服务端数据、不伪造请求**；关掉开关重启即恢复。 |
| 调用 `AccountSetTutorial` 正规接口 | ⚠️ 未接线（已探测） | 类/字段/发请求入口都在，但 `GameSessionManager.SendRequest` 需要 Session/PacketInfo/AES 上下文，没有 il2cpp dump（字段偏移）时硬拼会让网络层掉线。本轮改为**运行时签名探测**，把真实参数类型打进日志，下一轮可直接接线。 |
| 自动编队 | ⚠️ 未适配（已探测） | `MX.Data.DefaultSettingData.EchelonDBCreate / EchelonFormationCheckByIds / GetEchelon` 已定位并打签名日志；参数是对象，偏移未知时硬调会生成非法编队，故不调用。 |
| 选关 / 进战斗 | ✅ 交给 auto-story | 本模块只判断 `Config.autoBattle.enable`，关着就停并给出原因；开着就进入「等结算」阶段。 |
| 自动领任务奖励 | ⚠️ 未适配 | `MissionRewardNetworkTask / MissionRewardRequest` 已定位，但领奖是 UI 组件方法（`MissionContentBase.RequestMissionReward` 等）驱动，同样要过 `SendRequest`。UI 上该开关**置灰并标「未适配」**，不做“看起来能点”的死开关。 |
| 体力安全阀 | ⚠️ 未接线 | metadata 只有 `CurrencySnapshot.get_ActionPoint`（实例 getter），无静态入口 → `AutoFarmReadActionPoint()` 返回 -1（未知），阈值逻辑已写好但不会误触发。 |
| 连续 3 次失败 / 无法识别界面 → 停 | ✅ | `g_afFailStreak >= 3` → `AutoFarmStop(code=3)`；引导 hook 装不上 → `code=4`；未开自动战斗 → `code=5`。停止原因直接显示在面板。 |
| 每步间隔 ≥ 2 秒 | ✅ | `AutoFarmMainThreadTick()` 里 `now - g_afLastStepMs < 2000` 直接 return。 |

> UI 上只保留 3 个开关（总开关 / 跳引导 / 领奖）；`loopCount`、`staminaFloor` 先进配置结构备用，**没有做成面板滑条** —— 没接线的滑条就是死控件，等接线后再放出来。

## 2. 改动清单（行号按交付时文件状态）

### `Game/Config.h`
- 新增 `sAutoFarm` 结构（50-61 行）：`enableStarter / skipTutorial / claimMissionReward / loopCount / staminaFloor`
- `sConfig` 挂 `sAutoFarm autoFarm;`（90 行，紧跟 `autoBattle`）
- `int version = 12` → **13**（97 行）

### `Game/Config.cpp`
- `kCfgVersion = 12` → **13**（43 行）
- save 格式串 +5 行（250-254 行）、参数 +5 个（288-292 行）、load 分支 +5 条（457-462 行），风格照 `battle.*`

### `main.cpp`
- 852-854 行：`AutoFarmMainThreadTick()` 已有声明处补 `static void AutoFarmInstall();`
- **2473-2477 行**：`init_my_hook()` 内 `if (!g_safeMode) AutoFarmInstall();`（在 `InstallAutoBattleStory()` 之后、`InitUnityApi()` 之前）
- **2540-2940 行**：新增「新号一键起步」整段（枚举/状态/反射工具/引导 hook/探测/状态机）
- **3957-4001 行**：`DrawMainFeaturePage()` 内新增 UI 节（3 个 ToggleSwitch + 阶段/进度/停止原因/能力行 + 「复位起步状态」按钮）
- **5275-5278 行**：`ConfigFingerprint()` 补 `autoFarm` 5 个字段（不加会「改了开关不落盘」）

## 3. metadata 取证（`audit/ba-apk/out/metadata-strings.txt` 行号）

| 符号 | 行号 | 用途 |
|---|---|---|
| `AccountSetTutorialNetworkTask` | 29229 | 正规 SetTutorial 的 NetworkTask |
| `get_TutorialIds` / `set_TutorialIds` / `<TutorialIds>k__BackingField` / `TutorialIds` | 29230-29233 | 请求体字段（挂在 NetworkTask 上） |
| `AccountSetTutorialRequest` / `AccountSetTutorialResponse` | 72726 / 72727 | 协议包 |
| `Account_SetTutorial` | 73059 | 协议枚举名 |
| `AccountGetTutorialNetworkTask` | 29200 | 拉取已完成的教程列表 |
| `CampaignConfirmTutorialNetworkTask` | 29372 | 教程关确认（任务链另一段） |
| `CampaignSubStageResultNetworkTask`（同级） | — | 关卡结算 |
| `co_SyncTutorialCompletionIds` | 32190 | 客户端把本地完成 id 同步给服务端的协程（在 Account/Login 管理类上） |
| `GameSessionManager.SendRequest` | 135758 | 所有 NetworkTask 的统一发送入口 |
| `MX-Data-TutorialNewData-GetCompulsoryTutorialList0` | mx-names.txt 16537 | **本轮实际 hook 的方法** |
| `MX-Data-TutorialNewData-GetTutorialList0` | mx-names.txt 16538 | 已完成列表（只打印，不清空） |
| `MX-Data-DefaultSettingData-EchelonDBCreate0` | mx-names.txt 2398 | 自动编队入口（已探测） |
| `MX-Data-DefaultSettingData-EchelonFormationCheckByIds0` | mx-names.txt 2399 | 编队合法性校验（已探测） |
| `MX-Data-MissionData-GetAllMissions0` | mx-names.txt 16064 | 任务列表（已探测） |
| `MX-Data-MissionInfo-CanReceiveReward0` | mx-names.txt 16077 | 可领奖判定（已探测） |
| `MissionRewardNetworkTask-HandleMessage` | 137420 区段 | 领奖 NetworkTask（已探测） |
| `CurrencySnapshot-get_ActionPoint` | mx-names.txt 16989 | 体力（实例 getter，未接线） |

## 4. 运行时行为 / 日志（`adb logcat -s AzusaNative` 或 `azusa_native_log.txt`）

安装期（只在开关非全关时出现）：
```
[起步]安装开始（总开关=1 跳引导=1 领奖=0）
[起步]MX.Data.TutorialNewData.GetCompulsoryTutorialList=0x....
[起步]hook MX.Data.TutorialNewData.GetCompulsoryTutorialList=0x.... rc=0 old=0x....
[起步]正规接口 AccountSetTutorialNetworkTask=0x.... ns=... TutorialIds=0x....
[起步]签名 AccountSetTutorialNetworkTask.ProcessSession(....) argc=N ptr=0x....
[起步]签名 MX.Data.DefaultSettingData.EchelonDBCreate(....) argc=N ptr=0x....
[起步]签名 MX.Program.Scripts.Network.GameSessionManager.SendRequest(....) argc=N ptr=0x....
[起步]能力：引导旁路=已装｜正规SetTutorial=已探测｜编队=已探测(未接线)｜领奖=已探测(未接线)
```
运行期（引导列表被清空时，**每个 tutorialId 一条**）：
```
[起步]强制引导 tutorialId=100000（1/3）
[起步]强制引导已清空 3 条（客户端不再弹引导）
[起步]引导阶段：旁路=1 已跳过=3 条
[起步]进入推关阶段：战斗/结算交给 auto-story
```
停止：`[起步]停止 code=N 原因=...`（2=体力、3=连续失败、4=引导未适配、5=未开自动战斗）

## 5. 验证

- 用 NDK r27c 的 clang 对 `main.cpp`、`Game/Config.cpp` 做了 **`-fsyntax-only`**（同 `build_so.sh` 的 flag/target/`-I`）：**0 诊断、0 警告**。
- 未产出任何 .o/.so（不越权编译，最终由 lead 统一 `assembleRelease`）。
- 未在设备上运行（用户自行实测）。

## 6. 未适配项的下一步（接线所需数据）

1. 跑一次游戏，抓上面 4 条 `[起步]签名 ...` 日志 → 得到 `SendRequest` / `EchelonDBCreate` / `ProcessSession` 的真实参数类型与 argc。
2. 用这三个签名补：
   - `AutoFarmSyncTutorial()`：`il2cpp_object_new(AccountSetTutorialNetworkTask)` → 调 `set_TutorialIds(List<long>)` → `GameSessionManager.SendRequest(task)`；**开关与日志独立**（`[起步]同步 tutorialId=X`）。
   - `AutoFarmClaimMissions()`：`MissionData.GetAllMissions()` → 逐个 `MissionInfo.CanReceiveReward()` → 组 `MissionRewardRequest` → `SendRequest`。
   - `AutoFarmFormation()`：`DefaultSettingData.EchelonDBCreate(ids...)` + `EchelonFormationCheckByIds` 校验通过后再落盘。
3. 体力：等 `AccountData`/`CurrencySnapshot` 实例入口确定后实现 `AutoFarmReadActionPoint()`（现在返回 -1，安全阀不误触发）。

## 7. 风险

- 引导旁路清的是**游戏返回的 List 本身**（`List.Clear()`）。若某版本该 getter 返回的是内部长期持有的完成列表，清空等效于「这次登录认为全部引导已做过」，重启即恢复；不会写服务端。
- 所有新 hook 都是「取不到地址就不装」，绝不 hook 到 null；全关时 tick 首行 return，且不安装任何 hook。
- `AutoFarmProbe()` 会遍历全部程序集的类名（一次性，安装阶段），不做每帧扫描。
