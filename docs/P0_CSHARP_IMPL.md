# P0 抽卡概率可配置化 · C# 服务端实现报告

> 2026-11-19 02:5x　·　**只改源码 + 本地构建，未部署、未 SSH、未碰服务器任何文件**
> 源码树：`work\ba\srv_src\Shittim-Server\`　·　构建产物：`work\ba\srv_src\_build_p0rates\`
> 前置方案：`work\ba\plan\20261119\P0_GACHA_RATES_PLAN.md`（本报告按本次任务书的口径执行：**绝对阈值语义不动、默认值一分不差**，与旧方案里"改累加语义"的选项 A/B/C 无关）

---

## 0. 结论（先看这 5 行）

| 项 | 结果 |
|---|---|
| 改了什么 | 阈值从 `InitializeGachaRates()` 的 switch 常量 → `Data/gacha_rates.defaults.json`（默认）+ 可选 `Data/gacha_rates.json`（覆盖），mtime+长度 热加载；新增 3 个 `/api/admin/gacha/rates*` 端点 |
| **变了哪几个 DLL** | **只有 `Shittim-Server.dll` 一个**（69 个 DLL 逐一比对，其余 68 个 sha256 完全一致，`Schale.dll` 未动） |
| 新 DLL sha256 | `c013f4427ad01d44c00cc63af3de817b800638fcd8ec0ee55de41126aed106aa`（2,727,424 B，线上是 `160c3e15…` / 2,688,000 B） |
| 默认行为 | 15 个 `ShopCategoryType` × 1000 档逐项比对，**1000/1000 档位全部相同**；四主组 3★ 合计仍是 3.00% / 2.30% / 2.30% / 4.40% |
| 自测 | 74 项检查全过（`_build_p0rates\selftest\`，退出码 0）；含损坏回落、热加载、校验、备份保留 10 份 |

**基线可复现性（这条最重要）**：先用**未改动的源码**构建到 `_build_p0rates\baseline\`，得到的 `Shittim-Server.dll` sha256 = `160c3e159956ee8300b57a90af70bc8813cb03ce5aef48d3c36615631cf4bd16`，与 `HANDOVER_20261119.md §174` 记录的线上 DLL **逐位相同**。⇒ 本机源码树就是线上源码树，DLL 字节差异**只**来自本报告的改动。

---

## 1. 红线核查

| 红线 | 执行情况 |
|---|---|
| 不部署 / 不 SSH / 不碰服务器 | 全部操作只在本机 `work\ba\srv_src\` 与 `work\ba\plan\`；无任何网络调用、无 ssh/scp/curl 到线上 |
| 改前备份 `*.cs.bak_p0_<时间戳>` | `Services\GachaService.cs.bak_p0_20261119_023900`、`Shittim-Server.csproj.bak_p0_20261119_023900`、`CLI\GameServer.cs.bak_p0_20261119_023900` |
| 构建到新目录 | `_build_p0rates\`（主）+ `_build_p0rates\baseline\`（基线复现）+ `_build_p0rates\selftest\`（自测）；**未写** `bin\Release`、**未碰**任何既有 `_build_*` |
| `bin\Release` 未被覆盖 | 构建前后 `Shittim-Server\bin\Release\net10.0\Shittim-Server.dll` 与 `Schale\bin\Release\net10.0\Schale.dll` 的 **大小/mtime 完全未变**（`2687488 / 2026-11-18T16:44:00Z`、`5392896 / 2026-11-18T14:40:25Z`） |
| 不改 `ShopManager.cs:185/225-256` | `ShopManager.cs` **一个字节都没改**（文件 mtime 未变）。`InitializeGachaRates` 返回的仍是同一组"绝对上界"，判定阶梯原样保留 |
| 不改消耗/保底/`PickupDuplicateBonus` | 同上，未触碰 |
| 形态核对 | `InitializeGachaRates()` 确为 `switch`，确存在 `permanentSSRRate`，与任务书描述**完全一致**，无需停下 |

---

## 2. 改动文件清单（改前 → 改后）

### 2.1 `Shittim-Server\Services\GachaService.cs`（130 → 133 行）

**改前**（原 29-57 行）：

```csharp
    public static (long, long, long, long, long, bool) InitializeGachaRates(ShopCategoryType characterBannerType)
    {
        var (rateUpSSRRate, fesSSRRate, limitedSSRRate, permanentSSRRate, SRRate, isSelector) = (0, 0, 0, 0, 0, false);
        switch (characterBannerType)
        {
            case ShopCategoryType.NormalGacha:
                permanentSSRRate = 30;
                SRRate = 185;
                break;
            case ShopCategoryType.FesGacha:
                rateUpSSRRate = 7;
                fesSSRRate = 9;
                permanentSSRRate = 44;
                SRRate = 185;
                break;
            case ShopCategoryType.TicketGacha:
                isSelector = true;
                break;
            case ShopCategoryType.LimitedGacha:
            case ShopCategoryType.PickupGacha:
            default:
                rateUpSSRRate = 7;
                permanentSSRRate = 23;
                SRRate = 185;
                break;
        }

        return (rateUpSSRRate, fesSSRRate, limitedSSRRate, permanentSSRRate, SRRate, isSelector);
    }
```

**改后**（29-60 行，全文件）：

```csharp
    public static (long, long, long, long, long, bool) InitializeGachaRates(ShopCategoryType characterBannerType)
    {
        var (rateUpSSRRate, fesSSRRate, limitedSSRRate, permanentSSRRate, SRRate, isSelector) = (0, 0, 0, 0, 0, false);
        switch (characterBannerType)
        {
            case ShopCategoryType.TicketGacha:
                // Selection-ticket banners hand out the chosen character instead of rolling, so every rate stays 0 and isSelector says why.
                isSelector = true;
                break;
            // >>> BAPATCH-P0RATES v1 >>>
            // The four roll thresholds are no longer compiled-in constants. GachaRateConfig reads Data/gacha_rates.defaults.json,
            // overlays the optional Data/gacha_rates.json, and hot-reloads when either file changes. Its defaults are exactly the
            // numbers this switch used to hold (Normal 30/185, Fes 7/9/44/185, Pickup+Limited+everything else 7/23/185), so the odds
            // do not move until an operator edits the file. These are still ABSOLUTE upper bounds, not band widths: ShopManager's
            // `randomNumber < rate` ladder is untouched, which is why ssrThreshold is the total SSR cut-off and upSsrRate/fesSsrRate
            // must sit inside it. GachaRateConfig.GroupNameOf carries the old per-category mapping.
            case ShopCategoryType.NormalGacha:
            case ShopCategoryType.FesGacha:
            case ShopCategoryType.LimitedGacha:
            case ShopCategoryType.PickupGacha:
            default:
                var rates = GachaRateConfig.ForCategory(characterBannerType);
                rateUpSSRRate = rates.UpSsrRate;
                fesSSRRate = rates.FesSsrRate;
                permanentSSRRate = rates.SsrThreshold;
                SRRate = rates.SrRate;
                break;
            // <<< BAPATCH-P0RATES v1 <<<
        }

        return (rateUpSSRRate, fesSSRRate, limitedSSRRate, permanentSSRRate, SRRate, isSelector);
    }
```

要点：

- `TicketGacha` **优先短路**（`isSelector=true`，四率全 0），永不读配置 —— 与原来一致。
- `limitedSSRRate` 仍然固定 0（新 schema 里没有这个字段，`ShopManager:242` 的 `limitedSSRRate > 0` 分支照旧是死分支）。
- 两个调用点（`ShopManager.cs:160` 十连、`:334` `SimulateGacha` 概率统计页）都走同一个函数 ⇒ **统计页自动同步，没有第二份阈值代码要改**。

### 2.2 `Shittim-Server\Shittim-Server.csproj`（+7 行）

```diff
     <None Update="Data\GachaRecruitBanners.cn.json">
       <CopyToOutputDirectory>PreserveNewest</CopyToOutputDirectory>
     </None>
+    <!-- BAPATCH-P0RATES v1: shipped gacha roll thresholds. ... -->
+    <None Update="Data\gacha_rates.defaults.json">
+      <CopyToOutputDirectory>PreserveNewest</CopyToOutputDirectory>
+    </None>
```

### 2.3 `Shittim-Server\CLI\GameServer.cs`（+3 行）

```diff
                 Shittim_Server.Services.WorldRaidService.Load();
+                // BAPATCH-P0RATES v1: log the thresholds the gacha ladder will use (and any override file problem) at boot,
+                // so "the panel says 30 but the server rolls 23" is answerable from the log alone.
+                Shittim_Server.Services.GachaRateConfig.Preload();
```

启动日志（本次自测里已经真实跑出来，见 §6）：

```
[INF] [GachaRates] boot: override file absent, defaults=...\Data\gacha_rates.defaults.json, isDefault=True
[INF] [GachaRates] boot Normal: upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185
[INF] [GachaRates] boot Pickup: upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185
[INF] [GachaRates] boot Limited: upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185
[INF] [GachaRates] boot Fes: upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185
```

### 2.4 备份文件

| 文件 | 大小 |
|---|---|
| `Services\GachaService.cs.bak_p0_20261119_023900` | 4,763 B |
| `Shittim-Server.csproj.bak_p0_20261119_023900` | 4,136 B |
| `CLI\GameServer.cs.bak_p0_20261119_023900` | 13,288 B |

回滚：`Copy-Item <bak> <原名> -Force` 后重新构建即可（`Data\gacha_rates.defaults.json` 留着也不影响旧 DLL，旧 DLL 根本不读它）。

---

## 3. 新增文件清单

| 文件 | 行数 | 作用 |
|---|---|---|
| `Shittim-Server\Services\GachaRateConfig.cs` | 1007 | 配置提供者：schema 解析 + 校验 + 默认值合并 + mtime/长度 热加载 + 备份/原子写/保留 10 份 + 写操作日志。**任何读失败都回落默认值，绝不抛异常** |
| `Shittim-Server\Controllers\GachaRatesAdminController.cs` | 185 | 3 个管理端点（GET/POST `gacha/rates`、POST `gacha/rates/reset`），复用 `[Route("api/admin")]` + `[AdminAuth]`；请求体手工用 `JsonElement` 解析以便给出精确 400 文案 |
| `Shittim-Server\Data\gacha_rates.defaults.json` | 9 | 随程序发布的默认值（= 改动前的 6 个常量），`CopyToOutputDirectory` |
| `_build_p0rates\selftest\GachaRatesSelfTest.csproj` + `Program.cs` | 575 | 独立控制台自测（**不进主工程**），直接引用构建出来的 `_build_p0rates\Shittim-Server.dll` |

### 3.1 配置文件（最终形态，`Data\gacha_rates.defaults.json`，原文）

```json
{
  "version": 1,
  "groups": {
    "Normal": { "ssrThreshold": 30, "srRate": 185 },
    "Pickup": { "upSsrRate": 7, "ssrThreshold": 23, "srRate": 185 },
    "Limited": { "upSsrRate": 7, "ssrThreshold": 23, "srRate": 185 },
    "Fes": { "upSsrRate": 7, "fesSsrRate": 9, "ssrThreshold": 44, "srRate": 185 }
  }
}
```

覆盖文件 `Data\gacha_rates.json` **不随包发布**（不存在 = 纯默认）。写入时只写被显式设置过的字段，例如：

```json
{
  "version": 1,
  "groups": {
    "Normal": {
      "ssrThreshold": 40,
      "srRate": 200
    },
    "Pickup": {
      "ssrThreshold": 30
    }
  }
}
```

### 3.2 分组映射（照 `InitializeGachaRates()` 原 switch 的落桶，未自创）

| 分组 | 来源 `ShopCategoryType` | 默认值 |
|---|---|---|
| `Normal` | `NormalGacha`(6) | ssrThreshold 30 / srRate 185 |
| `Fes` | `FesGacha`(24) | up 7 / fes 9 / ssrThreshold 44 / srRate 185 |
| `Limited` | `LimitedGacha`(19) | up 7 / ssrThreshold 23 / srRate 185 |
| `Pickup` | `PickupGacha`(5) **+ 原 switch 的 `default:`**：`EventGacha`(8)、`TutoGacha`(11)、`PointGacha`(7)、`DirectPayGacha_DontUseGlobal`(23)、`BeforehandGacha`(32)、`GlobalSpecialGacha`(34)、`SelectPickupGacha`(35)、`SelectPickupFesGacha`(39)、`SelectPickupLimitedGacha`(40)、`RecruitSellection`(12) 等 | up 7 / ssrThreshold 23 / srRate 185 |
| （不落桶） | `TicketGacha`(22) | `isSelector=true`，四率恒 0，不读配置 |

⚠ `SelectPickupFesGacha` / `SelectPickupLimitedGacha` 在原 switch 里就是走 `default:` 的，所以**仍按 Pickup 算**，没有被"顺手修正"成 Fes —— 这是刻意保持零行为变化。

### 3.3 字段语义（写进代码注释，也写进 API）

- `ssrThreshold` = 原 `permanentSSRRate`，**它是总出彩上界**（不是区间宽度）。判定是 `randomNumber < permanentSSRRate`，所以 `[0, ssrThreshold)` 里的所有值都会出彩（`upSsrRate` / `fesSsrRate` 只是在这段里切出更早的专属档）。
- 每组 **3★ 合计 = ssrThreshold**（Normal 例外：本就没有 UP 档，同样等于 ssrThreshold）。面板按"总出彩率"展示即可。
- `upSsrRate`、`fesSsrRate` 是**绝对上界**，且必须 ≤ `ssrThreshold`（否则配置无意义 → 400）。
- 不做"求和 ≤ 1000"限制（任务书明确要求：语义是绝对阈值，累加和不代表任何东西）。

---

## 4. 实现要点

### 4.1 热加载（mtime + 长度）

- `GachaRateConfig.Current()` 每次被调用（= 每次十连/统计请求各一次）对比两个文件的 `(LastWriteTimeUtc.Ticks, Length)` 组成签名；签名未变直接返回缓存快照，变化则在锁内重读。
- 重读时若签名又变了（文件正被写），最多重试 3 次再接受，避免"读到半截文件后把错误状态缓存到下次变更"。
- 写操作内部：校验 → 备份 → 原子写（`.tmp` + `File.Move(overwrite)`）→ `Invalidate()` → **回读比对**；回读不一致就用备份回滚并返回错误。
- 读取失败/校验不过 → **整份回落默认值** + `Log.Warning(...)` + `GET` 里 `overrideFileValid:false` / `lastError`，**不抛异常**：抽卡永远拿得到一组可用阈值。
- 默认值三层：`Data\gacha_rates.defaults.json` → 代码内 `BuiltInDefaults()`（就是原来那 6 个常量）→ 永不为空。

### 4.2 校验（全部 400 + 明确错误，磁盘一字不动）

| 规则 | 错误样例 |
|---|---|
| 值必须是整数 0..1000 | `rates: Pickup.ssrThreshold must be between 0 and 1000 (got 1200)` |
| 小数/字符串/null 一律拒绝 | `rates: Pickup.ssrThreshold must be an integer between 0 and 1000 (got 1.5)` |
| 未知分组 | `rates: unknown group "Typo" (allowed: Normal, Pickup, Limited, Fes)` |
| 未知字段 | `rates: unknown field "ssrThresh" in group "Pickup" (allowed: upSsrRate, ssrThreshold, srRate)` |
| 该组没有的字段 | `rates: group "Normal" has no field "upSsrRate" (allowed: ssrThreshold, srRate)` |
| `ssrThreshold >= upSsrRate`（按**合并后**的生效值判断，部分覆盖也查） | `Pickup: ssrThreshold (5) must be >= upSsrRate (7)` |
| `ssrThreshold >= fesSsrRate` | `Fes: ssrThreshold (44) must be >= fesSsrRate (50)` |
| 顶层只允许 `version` / `groups` | `Data/gacha_rates.json: unknown top-level field "$schema" (allowed: version, groups)` |
| `scope` 只允许 `all`/四个组名 | `unknown scope "Typo" (allowed: all, Normal, Pickup, Limited, Fes)` |

非致命提示（写入成功但返回 `warnings`，不拦）：`srRate <= ssrThreshold` 时 SR 档永远抽不到，例如
`Pickup: srRate (185) <= ssrThreshold (300), so the SR band can never roll`。

### 4.3 备份与写日志

- 覆盖文件同目录：`gacha_rates.backup.<yyyyMMdd_HHmmss_fff>.json`（同毫秒撞名再加 `_2`），按文件名排序只留最近 **10** 份。
- 每次写/重置都记一行 INFO：**字段、旧值→新值、来源 IP、备份路径、写后生效值**：

```
[GachaRates] rates updated: ip=10.0.0.5 file=/www/wwwroot/ba_srv/Data/gacha_rates.json backup=/www/wwwroot/ba_srv/Data/gacha_rates.backup.20261119_024208_861.json changes=[Pickup.ssrThreshold 23 -> 30] effective=Normal{...} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=30, srRate=185} ...
[GachaRates] reset Pickup: ip=10.0.0.5 removed=[Pickup] fileDeleted=False backup=... effective=...
```

- 来源 IP 取 `X-Forwarded-For` 第一段 → `X-Real-IP` → `RemoteIpAddress`（线上走 nginx 时前两者才有意义）。
- 若 `../gacha_config.json`（旧 custom_rates 通道）仍非空，写操作额外打 WARN，并在 `GET` 返回 `legacyOverrideActive:true` —— 因为 `ShopManager.cs:193` 会让那份配置**整体接管**，不看本配置。

---

## 5. 构建

### 5.1 命令（可直接复制，工作目录 `work\ba\srv_src`）

```powershell
cd "C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src"

# ② 本次交付构建
dotnet build Shittim-Server\Shittim-Server.csproj -c Release -o _build_p0rates --nologo --no-incremental

# ③ 自测（独立工程，引用 ② 的产物 DLL）
cd _build_p0rates\selftest
dotnet build GachaRatesSelfTest.csproj -c Debug --nologo
dotnet bin\Debug\net10.0\GachaRatesSelfTest.dll
```

① 基线复现（只做一次，用来证明"本源码树 = 线上源码树"）：把上面第 ② 条原样对**未改动的源码**执行，只把 `-o` 换成 `-o _build_p0rates\baseline`：

```powershell
dotnet build Shittim-Server\Shittim-Server.csproj -c Release -o _build_p0rates\baseline --nologo --no-incremental
```

⇒ 产物 `_build_p0rates\baseline\Shittim-Server.dll` = `160c3e15…`（2,688,000 B），与线上一致。

- SDK：`dotnet 10.0.301`（`global.json` 要求 10.0.100 + `latestFeature`）
- 结果：**0 错误 / 268 警告**；警告数与改动前基线构建**完全相同**（268），新文件 `GachaRateConfig.cs`、`GachaRatesAdminController.cs` **零警告**。

### 5.2 主要产物

| 路径 | 大小 | sha256 |
|---|---|---|
| `_build_p0rates\Shittim-Server.dll` | 2,727,424 B | `c013f4427ad01d44c00cc63af3de817b800638fcd8ec0ee55de41126aed106aa` |
| `_build_p0rates\Shittim-Server.pdb` | 535,472 B | `b4d7f2771324a1e9f015917e5663adaa217ab539547c784adf9fedbb48b2bbd6` |
| `_build_p0rates\Data\gacha_rates.defaults.json` | 312 B | `59bbf27d738daa74f0693e53f8074ecefd469bdbaf5b5282aadf4d1d9e9b2aad` |
| `_build_p0rates\selftest\bin\Debug\net10.0\GachaRatesSelfTest.dll` | 自测程序 | 引用的 `Shittim-Server.dll` 副本 sha256 与上表**一致**（证明自测跑的就是交付产物） |

### 5.3 DLL 差异表（`_build_p0rates` vs 线上 `_build_envelope1`，69 个 DLL 全量比对）

| DLL | 线上大小 | 新大小 | 线上 sha256 | 新 sha256 | 变了？ |
|---|---|---|---|---|---|
| `Shittim-Server.dll` | 2,688,000 | 2,727,424 | `160c3e159956ee8300b57a90af70bc8813cb03ce5aef48d3c36615631cf4bd16` | `c013f4427ad01d44c00cc63af3de817b800638fcd8ec0ee55de41126aed106aa` | **✅ 变了** |
| 其余 68 个（`Schale.dll`、EF/Sqlite/Serilog/AutoMapper/FlatBuffers/…） | — | 同左 | — | 同左 | ❌ 一致 |

⇒ **只有 `Shittim-Server.dll` 一个 DLL 变了**（+39,424 B：新类 + 新控制器 + 启动一行）。

非 DLL 的附带变化（说明用）：

| 文件 | 变化 |
|---|---|
| `Shittim-Server.pdb` | 变了（调试符号必然变，不部署也不影响运行） |
| `Data\gacha_rates.defaults.json` | **新增**（必须随包上传） |
| `Shittim-Server.deps.json` | **未变**（没有新增 NuGet 依赖，实测 sha256 与线上一致） |
| 其余 76 个文件（appsettings/runtimes/web.config/…） | 未变 |

---

## 6. 自测

### 6.1 三种分布的结论表

**① 默认配置（改动前 = 改动后），1000 个随机值逐档计数**

| 分类 | 组 | UP 3★ | Fes 3★ | 限定 3★ | 常驻 3★ | 2★ | 1★ | 3★ 合计 |
|---|---|---|---|---|---|---|---|---|
| `NormalGacha` | Normal | 0 | 0 | 0 | 30 | 155 | 815 | 3.00% |
| `PickupGacha` | Pickup | 7 | 0 | 0 | 16 | 162 | 815 | 2.30% |
| `LimitedGacha` | Limited | 7 | 0 | 0 | 16 | 162 | 815 | 2.30% |
| `FesGacha` | Fes | 7 | 2 | 0 | 35 | 141 | 815 | 4.40% |
| 其余 10 个分类（Event/Tuto/Point/Beforehand/GlobalSpecial/SelectPickup×3/DirectPay/RecruitSellection） | Pickup | 7 | 0 | 0 | 16 | 162 | 815 | 2.30% |
| `TicketGacha` | —（isSelector） | 0 | 0 | 0 | 0 | 0 | 1000 | 不掷骰 |

（`常驻 3★=16` 就是 2.30% 里除了 UP 0.70% 之外的那 1.60%；`Fes 3★=2` 是因为 `fesSSRRate=9` 与 `rateUpSSRRate=7` 的绝对比较只留下 `[7,9)` 两档 —— 这就是**现状**，本次不改。）

**② 把 `Pickup.ssrThreshold` 改成 30（热加载，未重启、未调 Invalidate）**

| 分类 | UP 3★ | Fes 3★ | 常驻 3★ | 2★ | 1★ | 3★ 合计 |
|---|---|---|---|---|---|---|
| `PickupGacha`（改后） | 7 | 0 | 23 | 155 | 815 | **3.00%**（2.30% → 3.00%，符合预期） |
| `NormalGacha` / `LimitedGacha` / `FesGacha` | 不变 | 不变 | 不变 | 不变 | 不变 | 不变 |

**③ 配置文件损坏（8 种坏法）**

| 坏法 | 结果 |
|---|---|
| 截断 JSON / 空文件 / 二进制垃圾 | 解析失败 → 回落默认 + WARN，**不抛异常**，分布 = ① |
| 未知分组 / 未知字段 / `version` 非整数 | 校验失败 → 回落默认 + WARN，分布 = ① |
| `ssrThreshold < upSsrRate` | 交叉校验失败 → 回落默认 + WARN，分布 = ① |
| 值越界 9999 / 非整数 1.5 | 取值范围失败 → 回落默认 + WARN，分布 = ① |

### 6.2 自测输出全文

（命令：`cd _build_p0rates\selftest; dotnet bin\Debug\net10.0\GachaRatesSelfTest.dll`，退出码 **0**，末尾"检查 74 项，失败 0 项"）

```
==============================================================================
 P0 抽卡概率自测 · GachaRatesSelfTest
==============================================================================
运行时          : .NET 10.0.9
测试程序目录    : C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\
被测 DLL        : C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Shittim-Server.dll
覆盖文件        : C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json
默认值文件      : C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.defaults.json

[INF] （以下为服务端 GachaRateConfig.Preload() 的启动日志）
[INF] [GachaRates] boot: override file absent, defaults=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.defaults.json, isDefault=True
[INF] [GachaRates] boot Normal: upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185
[INF] [GachaRates] boot Pickup: upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185
[INF] [GachaRates] boot Limited: upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185
[INF] [GachaRates] boot Fes: upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185


------------------------------------------------------------------------------
 ① 默认配置：0..999 逐档分布（改动前 switch 常量 vs 改动后 GachaRateConfig）
------------------------------------------------------------------------------
  覆盖文件存在 = False    isDefault = True    version = 1
  defaults    = Normal(up=0,fes=0,ssr=30,sr=185) Pickup(up=7,fes=0,ssr=23,sr=185) Limited(up=7,fes=0,ssr=23,sr=185) Fes(up=7,fes=9,ssr=44,sr=185)

  [NormalGacha]  组=Normal
      改动前 (up=0,fes=0,lim=0,ssr=30,sr=185,sel=False)
      改动后 (up=0,fes=0,lim=0,ssr=30,sr=185,sel=False)
      改动前分布: UP 3★=0 Fes 3★=0 限定 3★=0 常驻 3★=30 2★=155 1★=815 (合计 1000)
      改动后分布: UP 3★=0 Fes 3★=0 限定 3★=0 常驻 3★=30 2★=155 1★=815 (合计 1000)
      [OK]   NormalGacha: 1000 个随机值逐档一致
  [PickupGacha]  组=Pickup
      改动前 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动后 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动前分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      改动后分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      [OK]   PickupGacha: 1000 个随机值逐档一致
  [LimitedGacha]  组=Limited
      改动前 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动后 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动前分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      改动后分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      [OK]   LimitedGacha: 1000 个随机值逐档一致
  [FesGacha]  组=Fes
      改动前 (up=7,fes=9,lim=0,ssr=44,sr=185,sel=False)
      改动后 (up=7,fes=9,lim=0,ssr=44,sr=185,sel=False)
      改动前分布: UP 3★=7 Fes 3★=2 限定 3★=0 常驻 3★=35 2★=141 1★=815 (合计 1000)
      改动后分布: UP 3★=7 Fes 3★=2 限定 3★=0 常驻 3★=35 2★=141 1★=815 (合计 1000)
      [OK]   FesGacha: 1000 个随机值逐档一致
  [TicketGacha]  组=Pickup  (isSelector=true，实际不掷骰)
      改动前 (up=0,fes=0,lim=0,ssr=0,sr=0,sel=True)
      改动后 (up=0,fes=0,lim=0,ssr=0,sr=0,sel=True)
      改动前分布: UP 3★=0 Fes 3★=0 限定 3★=0 常驻 3★=0 2★=0 1★=1000 (合计 1000)
      改动后分布: UP 3★=0 Fes 3★=0 限定 3★=0 常驻 3★=0 2★=0 1★=1000 (合计 1000)
      [OK]   TicketGacha: 1000 个随机值逐档一致
  [EventGacha]  组=Pickup
      改动前 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动后 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动前分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      改动后分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      [OK]   EventGacha: 1000 个随机值逐档一致
  [TutoGacha]  组=Pickup
      改动前 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动后 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动前分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      改动后分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      [OK]   TutoGacha: 1000 个随机值逐档一致
  [PointGacha]  组=Pickup
      改动前 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动后 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动前分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      改动后分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      [OK]   PointGacha: 1000 个随机值逐档一致
  [BeforehandGacha]  组=Pickup
      改动前 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动后 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动前分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      改动后分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      [OK]   BeforehandGacha: 1000 个随机值逐档一致
  [GlobalSpecialGacha]  组=Pickup
      改动前 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动后 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动前分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      改动后分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      [OK]   GlobalSpecialGacha: 1000 个随机值逐档一致
  [SelectPickupGacha]  组=Pickup
      改动前 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动后 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动前分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      改动后分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      [OK]   SelectPickupGacha: 1000 个随机值逐档一致
  [SelectPickupFesGacha]  组=Pickup
      改动前 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动后 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动前分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      改动后分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      [OK]   SelectPickupFesGacha: 1000 个随机值逐档一致
  [SelectPickupLimitedGacha]  组=Pickup
      改动前 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动后 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动前分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      改动后分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      [OK]   SelectPickupLimitedGacha: 1000 个随机值逐档一致
  [DirectPayGacha_DontUseGlobal]  组=Pickup
      改动前 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动后 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动前分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      改动后分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      [OK]   DirectPayGacha_DontUseGlobal: 1000 个随机值逐档一致
  [RecruitSellection]  组=Pickup
      改动前 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动后 (up=7,fes=0,lim=0,ssr=23,sr=185,sel=False)
      改动前分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      改动后分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
      [OK]   RecruitSellection: 1000 个随机值逐档一致

  四主组百分比（改动后 = 改动前，同一份默认值；不含十连第 10 抽保底）：
      档位        Normal     Pickup    Limited      Fes
      UP 3★          0.00%     0.70%     0.70%     0.70%
      Fes 3★         0.00%     0.00%     0.00%     0.20%
      限定 3★          0.00%     0.00%     0.00%     0.00%
      常驻 3★          3.00%     1.60%     1.60%     3.50%
      2★            15.50%    16.20%    16.20%    14.10%
      1★            81.50%    81.50%    81.50%    81.50%
      3★ 合计          3.00%     2.30%     2.30%     4.40%

      [OK]   Normal  = ssrThreshold 30 / srRate 185
      [OK]   Pickup  = up 7 / ssrThreshold 23 / srRate 185
      [OK]   Limited = up 7 / ssrThreshold 23 / srRate 185
      [OK]   Fes     = up 7 / fes 9 / ssrThreshold 44 / srRate 185
      [OK]   四主组 3★ 合计仍为 3.00% / 2.30% / 2.30% / 4.40%（绝对阈值语义未变）

------------------------------------------------------------------------------
 ② 默认值文件缺失：代码内兜底常量必须与默认值文件完全一致
------------------------------------------------------------------------------
[WRN] [GachaRates] C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.defaults.json is missing, using the built-in defaults (Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185})
  默认值文件已移走；isDefault=True, defaults.Pickup=GachaRateSet { UpSsrRate = 7, FesSsrRate = 0, SsrThreshold = 23, SrRate = 185 }
      [OK]   15 个分类的分布仍与改动前逐档一致
      [OK]   默认值文件恢复后 isDefault=true

------------------------------------------------------------------------------
 ③ 改配置立即生效：写文件后不重启、不调用 Invalidate，只靠 mtime + 长度 检测
------------------------------------------------------------------------------
[INF] [GachaRates] override file loaded (version 1, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=30, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
  写入 C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json
  内容 = {"version":1,"groups":{"Pickup":{"ssrThreshold":30}}}
  改动前 Pickup 分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=16 2★=162 1★=815 (合计 1000)
  改动后 Pickup 分布: UP 3★=7 Fes 3★=0 限定 3★=0 常驻 3★=23 2★=155 1★=815 (合计 1000)
      [OK]   Pickup.ssrThreshold 从 23 变成 30（无需重启，无需 Invalidate）
      [OK]   Pickup 的 upSsrRate / srRate 未被影响
      [OK]   Pickup 新分布 = UP7 / 常驻23 / 2★155 / 1★815
      [OK]   Normal / Limited / Fes 不受 Pickup 覆盖影响
      [OK]   服务端认为当前不是默认值 (isDefault=false)

------------------------------------------------------------------------------
 ④ 写入校验：GachaRateConfig.TryUpdate —— 就是 POST /api/admin/gacha/rates 内部调用的同一个函数
------------------------------------------------------------------------------
      [OK]   Pickup.ssrThreshold = 1200 (超范围) → 拒绝
          错误信息: rates: Pickup.ssrThreshold must be between 0 and 1000 (got 1200)
      [OK]   Pickup.ssrThreshold = -1 (负数) → 拒绝
          错误信息: rates: Pickup.ssrThreshold must be between 0 and 1000 (got -1)
      [OK]   Pickup.ssrThreshold = 1.5 (小数) → 拒绝
          错误信息: rates: Pickup.ssrThreshold must be an integer between 0 and 1000 (got 1.5)
      [OK]   Pickup.ssrThreshold = "30" (字符串) → 拒绝
          错误信息: rates: Pickup.ssrThreshold must be an integer between 0 and 1000 (got "30")
      [OK]   Pickup.ssrThreshold = null → 拒绝
          错误信息: rates: Pickup.ssrThreshold must be an integer between 0 and 1000 (got null)
      [OK]   Pickup = [] (不是对象) → 拒绝
          错误信息: rates: group "Pickup" must be a JSON object
      [OK]   Pickup.ssrThresh = 30 (未知字段) → 拒绝
          错误信息: rates: unknown field "ssrThresh" in group "Pickup" (allowed: upSsrRate, ssrThreshold, srRate)
      [OK]   Typo.{...} (未知分组) → 拒绝
          错误信息: rates: unknown group "Typo" (allowed: Normal, Pickup, Limited, Fes)
      [OK]   Normal.upSsrRate = 5 (Normal 没有该字段) → 拒绝
          错误信息: rates: group "Normal" has no field "upSsrRate" (allowed: ssrThreshold, srRate)
      [OK]   Pickup.ssrThreshold = 5 (< upSsrRate 7) → 拒绝
          错误信息: Pickup: ssrThreshold (5) must be >= upSsrRate (7)
      [OK]   Fes.fesSsrRate = 50 (> ssrThreshold 44) → 拒绝
          错误信息: Fes: ssrThreshold (44) must be >= fesSsrRate (50)
      [OK]   被拒绝的写入没有改动磁盘上的文件

[INF] [GachaRates] override file loaded (version 1, Normal, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=40, srRate=200} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=30, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] rates updated: ip=selftest file=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_398.json changes=[Normal.ssrThreshold 30 -> 40; Normal.srRate 185 -> 200] effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=40, srRate=200} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=30, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
      [OK]   Normal : ssrThreshold=40, srRate=200 → 接受
      备份文件: C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_398.json
      变更记录: Normal.ssrThreshold 30 -> 40; Normal.srRate 185 -> 200
      文件内容: {   "version": 1,   "groups": {     "Normal": {       "ssrThreshold": 40,       "srRate": 200     },     "Pickup": {       "ssrThreshold": 30     }   } }
      Normal 新分布: UP 3★=0 Fes 3★=0 限定 3★=0 常驻 3★=40 2★=160 1★=800 (合计 1000)
      [OK]   返回了备份文件路径且文件存在
      [OK]   磁盘文件写入了 Normal.ssrThreshold=40
      [OK]   Normal 新分布 = 常驻3★ 40 / 2★ 160 / 1★ 800
      [OK]   未提交的 Pickup 覆盖仍然保留 (ssrThreshold=30)

------------------------------------------------------------------------------
 ⑤ 恢复默认：scope=Pickup 只删该组覆盖，scope=all 删整份覆盖文件
------------------------------------------------------------------------------
      [OK]   前置：Normal=40 / Pickup=30
      [OK]   scope=Typo → 拒绝
          错误信息: unknown scope "Typo" (allowed: all, Normal, Pickup, Limited, Fes)
[INF] [GachaRates] override file loaded (version 1, Normal); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=40, srRate=200} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] reset Pickup: ip=selftest removed=[Pickup] fileDeleted=False backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_429.json effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=40, srRate=200} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
      [OK]   scope=Pickup → 接受
      备份文件: C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_429.json
      [OK]   Pickup 回落到默认 23
      [OK]   Pickup 的 ssrThreshold 回到默认且分布与改动前一致
      [OK]   Normal 的覆盖没有被 scope=Pickup 删掉
      [OK]   覆盖文件仍然存在（还剩 Normal 一组）
[INF] [GachaRates] reset all: ip=selftest removed=[Normal] fileDeleted=True backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_432.json effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
      [OK]   scope=all → 接受
      [OK]   scope=all 删掉了整份覆盖文件
      [OK]   四主组全部回到默认分布
      [OK]   服务端认为已恢复默认 (isDefault=true)
[INF] [GachaRates] reset all requested by ip=selftest; no override file present, nothing to remove
      [OK]   scope=all 重复调用仍然成功（幂等）

------------------------------------------------------------------------------
 ⑥ 备份：每次写前备份旧文件，同目录只保留最近 10 份
------------------------------------------------------------------------------
[INF] [GachaRates] override file loaded (version 1, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=21, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] rates updated: ip=selftest file=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json backup=(none) changes=[Pickup.ssrThreshold 23 -> 21] effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=21, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] override file loaded (version 1, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=22, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] rates updated: ip=selftest file=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_436.json changes=[Pickup.ssrThreshold 21 -> 22] effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=22, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] override file loaded (version 1, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] rates updated: ip=selftest file=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_437.json changes=[Pickup.ssrThreshold 22 -> 23] effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] override file loaded (version 1, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=24, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] rates updated: ip=selftest file=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_438.json changes=[Pickup.ssrThreshold 23 -> 24] effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=24, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] override file loaded (version 1, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=25, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] rates updated: ip=selftest file=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_440.json changes=[Pickup.ssrThreshold 24 -> 25] effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=25, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] override file loaded (version 1, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=26, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] rates updated: ip=selftest file=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_441.json changes=[Pickup.ssrThreshold 25 -> 26] effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=26, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] override file loaded (version 1, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=27, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] rates updated: ip=selftest file=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_442.json changes=[Pickup.ssrThreshold 26 -> 27] effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=27, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] override file loaded (version 1, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=28, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] rates updated: ip=selftest file=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_444.json changes=[Pickup.ssrThreshold 27 -> 28] effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=28, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] override file loaded (version 1, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=29, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] rates updated: ip=selftest file=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_445.json changes=[Pickup.ssrThreshold 28 -> 29] effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=29, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] override file loaded (version 1, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=30, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] rates updated: ip=selftest file=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_447.json changes=[Pickup.ssrThreshold 29 -> 30] effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=30, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] override file loaded (version 1, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=31, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] rates updated: ip=selftest file=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_448.json changes=[Pickup.ssrThreshold 30 -> 31] effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=31, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] override file loaded (version 1, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=32, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] rates updated: ip=selftest file=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_450.json changes=[Pickup.ssrThreshold 31 -> 32] effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=32, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
  连续写 12 次后，备份文件数 = 10
      最老: gacha_rates.backup.20261119_024503_437.json
      最新: gacha_rates.backup.20261119_024503_450.json
      [OK]   备份文件保留 10 份

------------------------------------------------------------------------------
 ⑦ 配置损坏 / 非法：回落默认 + WARN，绝不抛异常（抽卡不受影响）
------------------------------------------------------------------------------
[INF] [GachaRates] reset all: ip=selftest removed=[Pickup] fileDeleted=True backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_452.json effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[WRN] [GachaRates] Data/gacha_rates.json: not valid JSON (Expected depth to be zero at the end of the JSON payload. There is an open JSON object or array that should be closed. LineNumber: 0 | BytePositionInLine: 48.); falling back to the defaults
  [截断的 JSON] 不抛异常=True  回落默认=True  overrideFileValid=False
      lastError: Data/gacha_rates.json: not valid JSON (Expected depth to be zero at the end of the JSON payload. There is an open JSON object or array that should be closed. LineNumber: 0 | BytePositionInLine: 48.)
      WARN: [GachaRates] "Data/gacha_rates.json: not valid JSON (Expected depth to be zero at the end of the JSON payload. There is an open JSON object or array that should be closed. LineNumber: 0 | BytePositionInLine: 48.)"; falli…
      [OK]   截断的 JSON → 不抛异常且分布回到默认
[WRN] [GachaRates] Data/gacha_rates.json: not valid JSON (The input does not contain any JSON tokens. Expected the input to start with a valid JSON token, when isFinalBlock is true. LineNumber: 0 | BytePositionInLine: 0.); falling back to the defaults
  [空文件] 不抛异常=True  回落默认=True  overrideFileValid=False
      lastError: Data/gacha_rates.json: not valid JSON (The input does not contain any JSON tokens. Expected the input to start with a valid JSON token, when isFinalBlock is true. LineNumber: 0 | BytePositionInLine: 0.)
      WARN: [GachaRates] "Data/gacha_rates.json: not valid JSON (The input does not contain any JSON tokens. Expected the input to start with a valid JSON token, when isFinalBlock is true. LineNumber: 0 | BytePositionInLine: 0.)"; f…
      [OK]   空文件 → 不抛异常且分布回到默认
[WRN] [GachaRates] Data/gacha_rates.json: unknown group "Typo" (allowed: Normal, Pickup, Limited, Fes); falling back to the defaults
  [未知分组] 不抛异常=True  回落默认=True  overrideFileValid=False
      lastError: Data/gacha_rates.json: unknown group "Typo" (allowed: Normal, Pickup, Limited, Fes)
      WARN: [GachaRates] "Data/gacha_rates.json: unknown group \"Typo\" (allowed: Normal, Pickup, Limited, Fes)"; falling back to the defaults
      [OK]   未知分组 → 不抛异常且分布回到默认
[WRN] [GachaRates] Pickup: ssrThreshold (5) must be >= upSsrRate (7); falling back to the defaults
  [ssrThreshold < upSsrRate] 不抛异常=True  回落默认=True  overrideFileValid=False
      lastError: Pickup: ssrThreshold (5) must be >= upSsrRate (7)
      WARN: [GachaRates] "Pickup: ssrThreshold (5) must be >= upSsrRate (7)"; falling back to the defaults
      [OK]   ssrThreshold < upSsrRate → 不抛异常且分布回到默认
[WRN] [GachaRates] Data/gacha_rates.json: Pickup.ssrThreshold must be between 0 and 1000 (got 9999); falling back to the defaults
  [值越界 9999] 不抛异常=True  回落默认=True  overrideFileValid=False
      lastError: Data/gacha_rates.json: Pickup.ssrThreshold must be between 0 and 1000 (got 9999)
      WARN: [GachaRates] "Data/gacha_rates.json: Pickup.ssrThreshold must be between 0 and 1000 (got 9999)"; falling back to the defaults
      [OK]   值越界 9999 → 不抛异常且分布回到默认
[WRN] [GachaRates] Data/gacha_rates.json: Pickup.ssrThreshold must be an integer between 0 and 1000 (got 1.5); falling back to the defaults
  [非整数 1.5] 不抛异常=True  回落默认=True  overrideFileValid=False
      lastError: Data/gacha_rates.json: Pickup.ssrThreshold must be an integer between 0 and 1000 (got 1.5)
      WARN: [GachaRates] "Data/gacha_rates.json: Pickup.ssrThreshold must be an integer between 0 and 1000 (got 1.5)"; falling back to the defaults
      [OK]   非整数 1.5 → 不抛异常且分布回到默认
[WRN] [GachaRates] Data/gacha_rates.json: "version" must be an integer; falling back to the defaults
  [version 非整数] 不抛异常=True  回落默认=True  overrideFileValid=False
      lastError: Data/gacha_rates.json: "version" must be an integer
      WARN: [GachaRates] "Data/gacha_rates.json: \"version\" must be an integer"; falling back to the defaults
      [OK]   version 非整数 → 不抛异常且分布回到默认
[WRN] [GachaRates] Data/gacha_rates.json: not valid JSON ('P' is an invalid start of a value. LineNumber: 0 | BytePositionInLine: 0.); falling back to the defaults
  [二进制垃圾] 不抛异常=True  回落默认=True  overrideFileValid=False
      lastError: Data/gacha_rates.json: not valid JSON ('P' is an invalid start of a value. LineNumber: 0 | BytePositionInLine: 0.)
      WARN: [GachaRates] "Data/gacha_rates.json: not valid JSON ('P' is an invalid start of a value. LineNumber: 0 | BytePositionInLine: 0.)"; falling back to the defaults
      [OK]   二进制垃圾 → 不抛异常且分布回到默认
      [OK]   删掉损坏文件后恢复默认 (isDefault=true)

------------------------------------------------------------------------------
 ⑧ 管理 API 返回体：直接调用 GachaRatesAdminController（路由/鉴权由 [Route]+[AdminAuth] 负责，这里验的是返回 JSON）
------------------------------------------------------------------------------
[INF] [GachaRates] reset all requested by ip=selftest; no override file present, nothing to remove
  GET /api/admin/gacha/rates →
      {
        "ok": true,
        "rates": {
          "Normal": {
            "ssrThreshold": 30,
            "srRate": 185
          },
          "Pickup": {
            "upSsrRate": 7,
            "ssrThreshold": 23,
            "srRate": 185
          },
          "Limited": {
            "upSsrRate": 7,
            "ssrThreshold": 23,
            "srRate": 185
          },
          "Fes": {
            "upSsrRate": 7,
            "fesSsrRate": 9,
            "ssrThreshold": 44,
            "srRate": 185
          }
        },
        "defaults": {
          "Normal": {
            "ssrThreshold": 30,
            "srRate": 185
          },
          "Pickup": {
            "upSsrRate": 7,
            "ssrThreshold": 23,
            "srRate": 185
          },
          "Limited": {
            "upSsrRate": 7,
            "ssrThreshold": 23,
            "srRate": 185
          },
          "Fes": {
            "upSsrRate": 7,
            "fesSsrRate": 9,
            "ssrThreshold": 44,
            "srRate": 185
          }
        },
        "isDefault": true,
        "version": 1,
        "updatedAt": null,
        "filePath": "C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\srv_src\\_build_p0rates\\selftest\\bin\\Debug\\net10.0\\Data\\gacha_rates.json",
        "defaultsFilePath": "C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\srv_src\\_build_p0rates\\selftest\\bin\\Debug\\net10.0\\Data\\gacha_rates.defaults.json",
        "overrideFileExists": false,
        "overrideFileValid": false,
        "lastError": null,
        "warnings": [],
        "legacyOverrideActive": false,
        "legacyOverridePath": "C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\srv_src\\_build_p0rates\\selftest\\bin\\Debug\\gacha_config.json",
        "groupMapping": {
          "Normal": "ShopCategoryType.NormalGacha",
          "Pickup": "ShopCategoryType.PickupGacha and every category the server does not single out (default case)",
          "Limited": "ShopCategoryType.LimitedGacha",
          "Fes": "ShopCategoryType.FesGacha"
        },
        "backupFile": null,
        "changed": null,
        "resetScope": null,
        "overrideFileDeleted": null,
        "sourceIp": "unknown"
      }
      [OK]   GET 200 且 ok=true / isDefault=true
[INF] [GachaRates] override file loaded (version 1, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=30, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] rates updated: ip=unknown file=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json backup=(none) changes=[Pickup.ssrThreshold 23 -> 30] effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=30, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}

  POST /api/admin/gacha/rates  body={"rates":{"Pickup":{"ssrThreshold":30}}} →（此前没有覆盖文件，所以 backupFile=null）
      {
        "ok": true,
        "rates": {
          "Normal": {
            "ssrThreshold": 30,
            "srRate": 185
          },
          "Pickup": {
            "upSsrRate": 7,
            "ssrThreshold": 30,
            "srRate": 185
          },
          "Limited": {
            "upSsrRate": 7,
            "ssrThreshold": 23,
            "srRate": 185
          },
          "Fes": {
            "upSsrRate": 7,
            "fesSsrRate": 9,
            "ssrThreshold": 44,
            "srRate": 185
          }
        },
        "defaults": {
          "Normal": {
            "ssrThreshold": 30,
            "srRate": 185
          },
          "Pickup": {
            "upSsrRate": 7,
            "ssrThreshold": 23,
            "srRate": 185
          },
          "Limited": {
            "upSsrRate": 7,
            "ssrThreshold": 23,
            "srRate": 185
          },
          "Fes": {
            "upSsrRate": 7,
            "fesSsrRate": 9,
            "ssrThreshold": 44,
            "srRate": 185
          }
        },
        "isDefault": false,
        "version": 1,
        "updatedAt": "2026-11-18T18:45:03.7270059Z",
        "filePath": "C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\srv_src\\_build_p0rates\\selftest\\bin\\Debug\\net10.0\\Data\\gacha_rates.json",
        "defaultsFilePath": "C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\srv_src\\_build_p0rates\\selftest\\bin\\Debug\\net10.0\\Data\\gacha_rates.defaults.json",
        "overrideFileExists": true,
        "overrideFileValid": true,
        "lastError": null,
        "warnings": [],
        "legacyOverrideActive": false,
        "legacyOverridePath": "C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\srv_src\\_build_p0rates\\selftest\\bin\\Debug\\gacha_config.json",
        "groupMapping": {
          "Normal": "ShopCategoryType.NormalGacha",
          "Pickup": "ShopCategoryType.PickupGacha and every category the server does not single out (default case)",
          "Limited": "ShopCategoryType.LimitedGacha",
          "Fes": "ShopCategoryType.FesGacha"
        },
        "backupFile": null,
        "changed": [
          "Pickup.ssrThreshold 23 -> 30"
        ],
        "resetScope": null,
        "overrideFileDeleted": false,
        "sourceIp": "unknown"
      }
      [OK]   POST 200 且 isDefault=false / Pickup.ssrThreshold=30
      [OK]   首次写入没有旧文件 → backupFile=null
[INF] [GachaRates] override file loaded (version 1, Normal, Pickup); effective Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=40, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=30, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}
[INF] [GachaRates] rates updated: ip=unknown file=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.json backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_728.json changes=[Normal.ssrThreshold 30 -> 40] effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=40, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=30, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}

  POST /api/admin/gacha/rates  body={"rates":{"Normal":{"ssrThreshold":40}}} →（已有覆盖文件，返回备份路径）
      {
        "ok": true,
        "rates": {
          "Normal": {
            "ssrThreshold": 40,
            "srRate": 185
          },
          "Pickup": {
            "upSsrRate": 7,
            "ssrThreshold": 30,
            "srRate": 185
          },
          "Limited": {
            "upSsrRate": 7,
            "ssrThreshold": 23,
            "srRate": 185
          },
          "Fes": {
            "upSsrRate": 7,
            "fesSsrRate": 9,
            "ssrThreshold": 44,
            "srRate": 185
          }
        },
        "defaults": {
          "Normal": {
            "ssrThreshold": 30,
            "srRate": 185
          },
          "Pickup": {
            "upSsrRate": 7,
            "ssrThreshold": 23,
            "srRate": 185
          },
          "Limited": {
            "upSsrRate": 7,
            "ssrThreshold": 23,
            "srRate": 185
          },
          "Fes": {
            "upSsrRate": 7,
            "fesSsrRate": 9,
            "ssrThreshold": 44,
            "srRate": 185
          }
        },
        "isDefault": false,
        "version": 1,
        "updatedAt": "2026-11-18T18:45:03.7290005Z",
        "filePath": "C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\srv_src\\_build_p0rates\\selftest\\bin\\Debug\\net10.0\\Data\\gacha_rates.json",
        "defaultsFilePath": "C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\srv_src\\_build_p0rates\\selftest\\bin\\Debug\\net10.0\\Data\\gacha_rates.defaults.json",
        "overrideFileExists": true,
        "overrideFileValid": true,
        "lastError": null,
        "warnings": [],
        "legacyOverrideActive": false,
        "legacyOverridePath": "C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\srv_src\\_build_p0rates\\selftest\\bin\\Debug\\gacha_config.json",
        "groupMapping": {
          "Normal": "ShopCategoryType.NormalGacha",
          "Pickup": "ShopCategoryType.PickupGacha and every category the server does not single out (default case)",
          "Limited": "ShopCategoryType.LimitedGacha",
          "Fes": "ShopCategoryType.FesGacha"
        },
        "backupFile": "C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\srv_src\\_build_p0rates\\selftest\\bin\\Debug\\net10.0\\Data\\gacha_rates.backup.20261119_024503_728.json",
        "changed": [
          "Normal.ssrThreshold 30 -> 40"
        ],
        "resetScope": null,
        "overrideFileDeleted": false,
        "sourceIp": "unknown"
      }
      [OK]   第二次写入备份了旧文件

  POST /api/admin/gacha/rates  body={"rates":{"Pickup":{"ssrThreshold":1200}}} → 400
      {
        "ok": false,
        "error": "rates: Pickup.ssrThreshold must be between 0 and 1000 (got 1200)"
      }
      [OK]   非法值 → 400 且带明确错误信息
[INF] [GachaRates] reset all: ip=unknown removed=[Normal, Pickup] fileDeleted=True backup=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_p0rates\selftest\bin\Debug\net10.0\Data\gacha_rates.backup.20261119_024503_731.json effective=Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185}

  POST /api/admin/gacha/rates/reset  body={"scope":"all"} →
      {
        "ok": true,
        "rates": {
          "Normal": {
            "ssrThreshold": 30,
            "srRate": 185
          },
          "Pickup": {
            "upSsrRate": 7,
            "ssrThreshold": 23,
            "srRate": 185
          },
          "Limited": {
            "upSsrRate": 7,
            "ssrThreshold": 23,
            "srRate": 185
          },
          "Fes": {
            "upSsrRate": 7,
            "fesSsrRate": 9,
            "ssrThreshold": 44,
            "srRate": 185
          }
        },
        "defaults": {
          "Normal": {
            "ssrThreshold": 30,
            "srRate": 185
          },
          "Pickup": {
            "upSsrRate": 7,
            "ssrThreshold": 23,
            "srRate": 185
          },
          "Limited": {
            "upSsrRate": 7,
            "ssrThreshold": 23,
            "srRate": 185
          },
          "Fes": {
            "upSsrRate": 7,
            "fesSsrRate": 9,
            "ssrThreshold": 44,
            "srRate": 185
          }
        },
        "isDefault": true,
        "version": 1,
        "updatedAt": null,
        "filePath": "C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\srv_src\\_build_p0rates\\selftest\\bin\\Debug\\net10.0\\Data\\gacha_rates.json",
        "defaultsFilePath": "C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\srv_src\\_build_p0rates\\selftest\\bin\\Debug\\net10.0\\Data\\gacha_rates.defaults.json",
        "overrideFileExists": false,
        "overrideFileValid": false,
        "lastError": null,
        "warnings": [],
        "legacyOverrideActive": false,
        "legacyOverridePath": "C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\srv_src\\_build_p0rates\\selftest\\bin\\Debug\\gacha_config.json",
        "groupMapping": {
          "Normal": "ShopCategoryType.NormalGacha",
          "Pickup": "ShopCategoryType.PickupGacha and every category the server does not single out (default case)",
          "Limited": "ShopCategoryType.LimitedGacha",
          "Fes": "ShopCategoryType.FesGacha"
        },
        "backupFile": "C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\srv_src\\_build_p0rates\\selftest\\bin\\Debug\\net10.0\\Data\\gacha_rates.backup.20261119_024503_731.json",
        "changed": [
          "all groups -> defaults (Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185} Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185} Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185})"
        ],
        "resetScope": "all",
        "overrideFileDeleted": true,
        "sourceIp": "unknown"
      }
      [OK]   reset all → 200 且 isDefault=true / overrideFileDeleted=true

  POST /api/admin/gacha/rates/reset  body={"scope":"Typo"} → 400
      {
        "ok": false,
        "error": "unknown scope \"Typo\" (allowed: all, Normal, Pickup, Limited, Fes)"
      }
      [OK]   非法 scope → 400
      [OK]   请求体带未知顶层字段 → 400

  未知顶层字段 → 400 {
  "ok": false,
  "error": "unknown field \"extra\" in the request body (allowed: rates)"
}
[INF] [GachaRates] reset all requested by ip=selftest; no override file present, nothing to remove

==============================================================================
 结论：检查 74 项，失败 0 项 —— 全部通过
==============================================================================
```

---

## 7. 管理 API（curl 示例）

鉴权方式与现有 `/api/admin/*` 完全一致：类上挂 `[AdminAuth]`，`X-Admin-Key` 头（未配 key 时仅允许回环地址）。密钥用占位符 `ADMIN_KEY`。

> 下面四段是按线上路径（`/www/wwwroot/ba_srv/`）整理的示例。**同一份 JSON 的实测原文**见 §6.2 第 ⑧ 段 —— 那段是自测里直接实例化 `GachaRatesAdminController` 打出来的（只把路径换成了本机构建目录，字段名/结构完全一致）。

### 7.1 读当前值 + 默认值 + 文件状态

```bash
curl -s -H "X-Admin-Key: ADMIN_KEY" \
  http://127.0.0.1:5000/api/admin/gacha/rates
```

```json
{
  "ok": true,
  "rates": {
    "Normal":  { "ssrThreshold": 30, "srRate": 185 },
    "Pickup":  { "upSsrRate": 7, "ssrThreshold": 23, "srRate": 185 },
    "Limited": { "upSsrRate": 7, "ssrThreshold": 23, "srRate": 185 },
    "Fes":     { "upSsrRate": 7, "fesSsrRate": 9, "ssrThreshold": 44, "srRate": 185 }
  },
  "defaults": {
    "Normal":  { "ssrThreshold": 30, "srRate": 185 },
    "Pickup":  { "upSsrRate": 7, "ssrThreshold": 23, "srRate": 185 },
    "Limited": { "upSsrRate": 7, "ssrThreshold": 23, "srRate": 185 },
    "Fes":     { "upSsrRate": 7, "fesSsrRate": 9, "ssrThreshold": 44, "srRate": 185 }
  },
  "isDefault": true,
  "version": 1,
  "updatedAt": null,
  "filePath": "/www/wwwroot/ba_srv/Data/gacha_rates.json",
  "defaultsFilePath": "/www/wwwroot/ba_srv/Data/gacha_rates.defaults.json",
  "overrideFileExists": false,
  "overrideFileValid": false,
  "lastError": null,
  "warnings": [],
  "legacyOverrideActive": false,
  "legacyOverridePath": "/www/wwwroot/gacha_config.json",
  "groupMapping": {
    "Normal": "ShopCategoryType.NormalGacha",
    "Pickup": "ShopCategoryType.PickupGacha and every category the server does not single out (default case)",
    "Limited": "ShopCategoryType.LimitedGacha",
    "Fes": "ShopCategoryType.FesGacha"
  },
  "backupFile": null,
  "changed": null,
  "resetScope": null,
  "overrideFileDeleted": null,
  "sourceIp": "127.0.0.1"
}
```

（`backupFile` / `changed` / `resetScope` / `overrideFileDeleted` 在 GET 上一律为 `null`，只有写接口才填。）

### 7.2 改一组的值（部分字段合并，不传的字段保留）

```bash
curl -s -X POST -H "X-Admin-Key: ADMIN_KEY" -H "Content-Type: application/json" \
  -d '{"rates":{"Pickup":{"ssrThreshold":30}}}' \
  http://127.0.0.1:5000/api/admin/gacha/rates
```

```json
{
  "ok": true,
  "rates": {
    "Normal":  { "ssrThreshold": 30, "srRate": 185 },
    "Pickup":  { "upSsrRate": 7, "ssrThreshold": 30, "srRate": 185 },
    "Limited": { "upSsrRate": 7, "ssrThreshold": 23, "srRate": 185 },
    "Fes":     { "upSsrRate": 7, "fesSsrRate": 9, "ssrThreshold": 44, "srRate": 185 }
  },
  "defaults": { "...": "同上，不变" },
  "isDefault": false,
  "version": 1,
  "updatedAt": "2026-11-19T02:42:08.8610000Z",
  "overrideFileExists": true,
  "overrideFileValid": true,
  "lastError": null,
  "warnings": [],
  "legacyOverrideActive": false,
  "backupFile": "/www/wwwroot/ba_srv/Data/gacha_rates.backup.20261119_024208_861.json",
  "changed": ["Pickup.ssrThreshold 23 -> 30"],
  "resetScope": null,
  "overrideFileDeleted": false,
  "sourceIp": "10.0.0.5"
}
```

- `backupFile` 只在**写之前已经存在覆盖文件**时才有值；第一次写入（此前没有 `gacha_rates.json`）返回 `"backupFile": null`，因为没有旧文件可备份。第二次写入起就有路径了 —— 这两种情况的实测原文都在 §6.2 第 ⑧ 段。
- `updatedAt` 是覆盖文件的 `LastWriteTimeUtc`，ISO-8601 带 `Z`。
- 保存后**下一次抽卡就生效**（≤ 一次请求，无需重启）。

### 7.3 恢复默认

```bash
# 只恢复一组
curl -s -X POST -H "X-Admin-Key: ADMIN_KEY" -H "Content-Type: application/json" \
  -d '{"scope":"Pickup"}' http://127.0.0.1:5000/api/admin/gacha/rates/reset

# 全部恢复（删掉整份覆盖文件）
curl -s -X POST -H "X-Admin-Key: ADMIN_KEY" -H "Content-Type: application/json" \
  -d '{"scope":"all"}' http://127.0.0.1:5000/api/admin/gacha/rates/reset
```

```json
{
  "ok": true,
  "rates": { "...": "四组均等于 defaults" },
  "isDefault": true,
  "overrideFileExists": false,
  "backupFile": "/www/wwwroot/ba_srv/Data/gacha_rates.backup.20261119_024208_187.json",
  "changed": ["all groups -> defaults (...)"],
  "resetScope": "all",
  "overrideFileDeleted": true
}
```

`scope=all` 在文件本来就不存在时也返回 200（幂等），`backupFile:null`、`overrideFileDeleted:false`。

### 7.4 校验失败（400，磁盘不动）

```bash
curl -s -X POST -H "X-Admin-Key: ADMIN_KEY" -H "Content-Type: application/json" \
  -d '{"rates":{"Pickup":{"ssrThreshold":1200}}}' \
  http://127.0.0.1:5000/api/admin/gacha/rates
# HTTP 400
{"ok":false,"error":"rates: Pickup.ssrThreshold must be between 0 and 1000 (got 1200)"}
```

```bash
curl -s -X POST -H "X-Admin-Key: ADMIN_KEY" -H "Content-Type: application/json" \
  -d '{"rates":{"Pickup":{"ssrThreshold":5}}}' \
  http://127.0.0.1:5000/api/admin/gacha/rates
# HTTP 400
{"ok":false,"error":"Pickup: ssrThreshold (5) must be >= upSsrRate (7)"}
```

---

## 8. 部署前 srv-ops 要做的事

> 本报告没有执行任何一条；下面是交给 srv-ops 的清单。

1. **上传 1 个 DLL**：`_build_p0rates\Shittim-Server.dll` → `/www/wwwroot/ba_srv/Shittim-Server.dll`
   - 校验：`sha256sum Shittim-Server.dll` 应为 `c013f4427ad01d44c00cc63af3de817b800638fcd8ec0ee55de41126aed106aa`（2,727,424 B）
   - `Schale.dll` 及其余 67 个 DLL **不用动**（sha256 与线上一致）
2. **上传 1 个新数据文件**：`_build_p0rates\Data\gacha_rates.defaults.json` → `/www/wwwroot/ba_srv/Data/gacha_rates.defaults.json`
   - `Data\` 目录已存在（`Data\GachaRecruitBanners.cn.json` 就在里面），**不用建目录**
   - 768/644 权限即可（只读）
3. **不要**上传 `gacha_rates.json`（覆盖文件）—— 它由管理站在运行时创建；不存在 = 默认值
4. **重启进程**（DLL 换了，必须重启；改概率值本身以后不用重启）
   - 按 `_panel\PANEL_MERGE_20261117.md §4.1`：tmux 里 `kill-session` + `new-session`，`send-keys C-c` 会毁掉整个会话
   - **会踢掉当时所有在线玩家**，挑维护窗口
5. 重启后确认启动日志出现 5 行 `[GachaRates] boot ...`（阈值 + 是否加载了覆盖文件）
6. 检查旧通道：`ls -l /www/wwwroot/gacha_config.json`。若存在且 `custom_rates` 非空，`ShopManager.cs:193` 会让它**整体接管**，本配置不生效；`GET /api/admin/gacha/rates` 会返回 `legacyOverrideActive:true`
7. 冒烟：`GET /api/admin/gacha/rates` 应返回 `isDefault:true`、四组 = 默认值、`filePath` 指向 `/www/wwwroot/ba_srv/Data/gacha_rates.json`
8. 回滚：把上一版 `Shittim-Server.dll` 换回去再重启一次即可（`Data\gacha_rates.defaults.json` 留着无害，旧 DLL 不读它）

---

## 9. 已知边界（都是刻意的，不是缺陷）

1. **绝对阈值语义没修**：Pickup 3★ 仍是 2.30%（UP 0.70% + 常驻 1.60%）、Fes 仍是 4.40%（UP 0.70% + Fes 0.20% + 常驻 3.50%）。任务书要求"出率一分不差"，所以没有按旧方案的选项 A 改成累加。
2. **`limitedSSRRate` 不在 schema 里**，恒 0（`ShopManager:242` 的分支照旧不可达）。要开限定档得先扩 schema。
3. **旧 `gacha_config.json` 优先级更高**：`custom_rates` 非空时整体接管，会让本配置"改了不生效"。没动 `ShopManager.cs:193`（任务书要求不动该文件），但通过 `legacyOverrideActive` + 写操作 WARN 把这件事变可见。
4. **`srRate <= ssrThreshold` 只警告不拦**：此时 SR 档永远不会命中（2★ 只剩十连第 10 抽保底）。这是"可配置"的合法后果，由面板提示。
5. **5 秒/逐请求热加载窗口**：写文件与下一抽之间若正好有请求，可能用旧值；写路径是原子替换 + 写后 `Invalidate()`，所以管理站保存后"下一抽"一定是新值。
6. **备份按文件名排序**（时间戳定宽），清理只删最老的；跨进程同时写不在设计范围内（单进程服务）。
