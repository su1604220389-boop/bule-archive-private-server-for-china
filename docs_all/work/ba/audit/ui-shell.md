# EngineShell 外壳 v0.2 · Compose 重写与美化 交付报告

- 负责人：ui-polish（第 1 层工程，外壳线）
- 工作区：`$WS = /data/user/0/com.ai.assistance.operit/files/workspace/9dc0fd0c-7cad-4366-8d0b-bad7165d8587`
- 交付物：`$WS/dist/EngineShell_v0.2.apk`、本文件
- 结论：**Java+XML 外壳已整体替换为 Kotlin + Jetpack Compose；CoreApi/CoreListener/TaskPlan/NativeBridge/MockCore 接口层零改动；APK 构建成功且可安装。**

## 0. 结论速览

| 项 | 值 |
| --- | --- |
| APK | `$WS/dist/EngineShell_v0.2.apk`（与 `app/build/outputs/apk/debug/app-debug.apk` 同一文件） |
| 大小 | 11,729,521 B（v0.1 为 6,754,144 B，Compose 运行时约 +5 MB） |
| SHA-256 | `f476536233db292fab0bec305fc2a0fcb8c014aca764d8fa8e44446b5b7ba682` |
| versionName / versionCode | `0.2` / `2` |
| 包名 / 启动 Activity | `com.engineshell.app` / `com.engineshell.app.MainActivity` |
| compileSdk / targetSdk / minSdk | 35 / 34 / 23 |
| 构建 | `BUILD SUCCESSFUL in 29s`（gradle 8.7 + JDK 17.0.20.1 + AGP 8.1.4） |
| 签名 | Android Debug 证书，`apksigner verify` 通过 |
| 原生 so | APK 内 `lib/` 条目 0 个 → `NativeBridge.loadLibrary("enginecore")` 必失败 → 默认走 **MockCore** 演示核心（设计预期） |

## 1. 改动概览

| 类型 | 内容 |
| --- | --- |
| 新增 | `MainActivity.kt`（ComponentActivity + `setContent`） |
| 新增 | `ui/ShellRoot.kt`（深色背景 + Scaffold + 胶囊底部导航 + 页面切换 + 统一 Snackbar） |
| 新增 | `ui/HomeScreen.kt`、`ui/TaskScreen.kt`、`ui/ParamScreen.kt`、`ui/LogScreen.kt` |
| 新增 | `ui/UiKit.kt`（卡片/状态胶囊/图标块/指标格/幽灵按钮/大圆按钮/环形进度/日志行） |
| 复用 | `ui/ShellState.kt`（上一轮已建：Java 核心对象的 Compose 可观察镜像，本轮原样保留并通过编译） |
| 复用 | `ui/theme/Color.kt`、`ui/theme/Theme.kt`（深色 M3 方案 + 排版/圆角尺度，本轮原样保留） |
| 删除 | `MainActivity.java`、`ui/HomeFragment.java`、`ui/TaskFragment.java`、`ui/ParamFragment.java`、`ui/LogFragment.java`、`ui/LogAdapter.java`、`ui/RingProgressView.java`、`res/layout/*`（8 个 XML）、`res/menu/bottom_nav.xml` |
| 未动 | `core/*.java`（10 个）、`config/*.java`（2 个）、`res/drawable/*`（17 个矢量/形状）、`res/values/*`、`AndroidManifest.xml`、启动图标 |

备份（回滚用）：`$WS/.backup/EngineShell_precompose_ui_1019.tar.gz`（含改动前 `app/src` + `build.gradle`/`settings.gradle`/`gradle.properties`），另有 v0.1 完整内容 `$WS/.backup/EngineShell_xml_v01_0956.tar.gz`。

## 2. 构建配置核对（未改，逐项确认）

| 要求 | 实际 | 位置 |
| --- | --- | --- |
| Kotlin 1.9.22 | `ext.kotlin_version = '1.9.22'` | `build.gradle:3` |
| Compose BOM 2024.02.02 | `ext.compose_bom = '2024.02.02'`，`platform("androidx.compose:compose-bom:$compose_bom")` | `build.gradle:5`、`app/build.gradle:50` |
| Compose 编译器 1.5.8 | `kotlinCompilerExtensionVersion rootProject.ext.compose_compiler` | `app/build.gradle:32-34` |
| `buildFeatures.compose true` | 已开 | `app/build.gradle:28-30` |
| `org.gradle.jvmargs=-Xmx2560m` | `-Xmx2560m -XX:MaxMetaspaceSize=512m` | `gradle.properties:1` |
| aapt2 覆盖 | `android.aapt2FromMavenOverride=/root/Android/build-tools/35.0.0/aapt2` | `gradle.properties:10` |

> 构建前 `df -h /data`：218G 总量 / 19G 可用（92% 已用），Compose 依赖下载与构建无空间风险。

## 3. 视觉规范 → 代码映射

| 需求 | 实现位置 | 要点 |
| --- | --- | --- |
| 深色：背景 #12141C / 卡片 #1A1D28 / 主色 #6C5CE7 / 描边 #2A2E3A | `ui/theme/Color.kt` `Palette`（与 `res/values/colors.xml` 同值） | 两端同步，XML 主题与 Compose 主题不会串色 |
| 卡片 20dp 圆角 + 1dp 描边 + 垂直渐变 | `UiKit.kt:ShellCard` | `clip(RoundedCornerShape(20.dp))` + `Brush.verticalGradient(cardAlt → card)` + `border(1.dp, stroke)` |
| 首页 Canvas 环形进度（drawArc + SweepGradient + 双层发光） | `UiKit.kt:RingProgress` | 底环 `track`；内圈 60 格刻度（每 5 格加亮）；发光弧 `2.9×/1.9×` 线宽、alpha 0.14/0.26；主弧 `Brush.sweepGradient(brandDeep→brand→brandLight→mint→brandDeep)`；端点 mint 高光；进度 `animateFloatAsState(tween 700)` |
| 大圆按钮按压缩放 0.94 | `UiKit.kt:CircleActionButton` | `MutableInteractionSource + collectIsPressedAsState` → `animateFloatAsState(0.94f/1f, tween 120)`；运行中整体切危险色渐变 + 外层光晕随状态呼吸 |
| 阶段文字 AnimatedContent | `HomeScreen.kt` 阶段行 | `AnimatedContent(targetState = stage, fadeIn 220ms togetherWith fadeOut 140ms)` |
| 底部 M3 NavigationBar 胶囊指示器 | `ShellRoot.kt:ShellBottomBar` | `Surface(navBar)` + 每项 `Box(54×28dp, brand alpha 0.16×indicator)` 胶囊，`animateFloatAsState` + `animateColorAsState` 过渡；图标用 `res/drawable/ic_home|ic_task|ic_tune|ic_log` |
| 任务页卡片 + Switch + 错落淡入 | `TaskScreen.kt` | `StaggerItem` 每张卡 `delay(70ms × index)` 后 `fadeIn(280ms) + slideInVertically(320ms)`；Switch 自定义 `SwitchDefaults.colors`；整卡可点，与 Switch 双向一致 |
| 参数页 Slider `valueRange` 从阈值起 | `ParamScreen.kt` | `valueRange = item.min..item.max`，物理上拖不到下限以下；`onValueChange` 走 `ParamSpec.Item.normalize()` 吸附步长（`steps = 0` 以避免 489 枚刻度绘制开销） |
| 参数页 OutlinedTextField 钳制 + Snackbar | `ParamScreen.kt` | 只允许数字、最长 7 位；「应用 / IME Done」→ `normalize()` 钳制到 `[min,max]`；被改动时 `notify("已钳制到 …")`；滑条变动通过 `LaunchedEffect(value)` 回灌输入框 |
| 日志页 LazyColumn 等宽字体自动滚底 | `LogScreen.kt` | `FontFamily.Monospace`；`LaunchedEffect(logs.size) { animateScrollToItem(last) }`；前缀着色 `[Mock]`/`[shell]`/`[core]` |
| 统一提示 | `ShellRoot.kt` | 单一 `SnackbarHostState`，`currentSnackbarData?.dismiss()` 后 `showSnackbar`，避免排队堆积 |

补充美化：页面顶层 `verticalGradient(bg → bgDeep)` + 顶部品牌径向光晕（Canvas `radialGradient`，alpha 0.26）；页面切换 `AnimatedContent` 左右 1/12 位移淡入；首页「运行环境」「最近日志」卡片；任务页底部「开始执行/停止」二次入口。

## 4. 接口层保留证明（要求逐项）

| 接口 | 文件 | md5 | 结论 |
| --- | --- | --- | --- |
| `CoreApi` | `core/CoreApi.java` | `2bf5bcbe1288954e9a6fc63dac349385` | 未改动（mtime 09:05） |
| `CoreListener` | `core/CoreListener.java` | `fb915cab6a6c444fe6ce4cb1bf46163b` | 未改动 |
| `TaskPlan` | `core/TaskPlan.java` | `7ba805e1de6900c86176b3c6b93699d9` | 未改动（含 `toJson()`/`copy()`） |
| `NativeBridge` | `core/NativeBridge.java` | `80b560530c2359af885c7829d6866d3a` | 未改动，静态块 `try { System.loadLibrary("enginecore") } catch (Throwable)` 保留 |
| `MockCore` | `core/MockCore.java` | `7399d07e3f9ea66461a8323e1a42c932` | 未改动：300ms 推进 / 600ms 日志 / 10~20 tick（3~6s）结束 |
| `CoreProvider` / `CoreHub` / `NativeCore` / `LogRepository` / `ShellSession` | `core/*` | 见上表同目录 | 未改动 |
| 参数常量 | `config/ParamSpec.java`、`config/AppConfig.java` | `4b1bda…` / `97b23a…` | 未改动 |

Compose 侧只通过 `ShellState`（对象单例 + `mutableStateOf/StateList`）读写上述 Java 层；`ShellState.start()` 走 `hub.start(plan)`，`plan` 仍是 `ShellSession.plan()` 同一实例，`TaskPlan.copy()` 后交给 `CoreApi`。

APK 内类存在性（dex 字符串统计）：`CoreApi` 2、`TaskPlan` 6、`NativeBridge` 2、`MockCore` 3、`CoreHub` 3、`ShellState` 4、`ShellRoot` 19 处符号命中；`classes6.dex` 集中 428 处 UI 类符号。

## 5. 构建与验证记录

```
cd $WS/EngineShell
/root/gradle-8.7/bin/gradle --no-daemon --console=plain :app:assembleDebug
```

| 轮次 | 结果 | 说明 |
| --- | --- | --- |
| build1 | FAILED (2m14s) | `HomeScreen.kt:155 No value passed for parameter 'onClick'` —— 尾随 lambda 落到了 `modifier` 形参 |
| build2 | SUCCESS (47s) | 修掉 onClick 传参，首个 Compose APK 产出 |
| build3 | SUCCESS (34s) | 加任务页底部「开始执行/停止」入口，`notify` 形参被使用 |
| build4（最终） | **SUCCESS (29s)** | Slider 改 `steps = 0`（吸附逻辑保留），产物即交付 APK |

其他校验：

- `aapt2 dump badging`：`versionCode='2' versionName='0.2'`、`targetSdkVersion:'34'`、`launchable-activity: name='com.engineshell.app.MainActivity'`
- `apksigner verify --print-certs`：`CN=Android Debug`，SHA-256 `354d84da…906d1`（可安装）
- `unzip -Z1 | grep '^lib/'`：0 条 → 无 native 实现，MockCore 回退路径就是默认路径
- 编译告警仅 2 条：`statusBarColor/navigationBarColor` setter 在 API 35 已废弃（保留以兼容 23~34，运行时无影响）

## 6. 未验证项与风险

1. **未在真机安装运行**（按约定测试由用户执行）。本报告只能保证：编译通过、APK 结构/签名/启动 Activity 正确、接口类齐备。首次启动的实际渲染与点击流程需用户实测。
2. 体积从 6.75 MB 涨到 11.73 MB：debug 未压缩 + Compose runtime/foundation/animation/material3 约 +5 MB；后续要瘦身可只保留 `foundation + material3`、去掉 `appcompat/constraintlayout/recyclerview` 依赖。
3. 页面切换用 `AnimatedContent`，切走时该页局部 UI 状态（如输入框草稿）丢弃；业务状态都在 `ShellState`，不受影响。
4. `Slider steps=0` 是有意选择：`stamina` 若用离散 steps 会画 179 枚刻度、青辉石 479 枚，绘制开销大且视觉噪音重；数值仍按 `step` 吸附。
5. `minSdk 23`：Compose 1.6 最低要求 21，满足；Android 6 及以下无法安装。
6. `zipalign -c` 在本机执行报 `Illegal instruction`（该 build-tools 二进制与设备 ABI 不匹配的环境问题，非 APK 问题）；APK 由 AGP `packageDebug` 产出，对齐由 AGP 完成。

## 7. 回滚方式

```bash
cd $WS
tar xzf .backup/EngineShell_precompose_ui_1019.tar.gz    # 恢复 Java+XML 外壳到可编译态
# 或恢复上一交付版本
cp dist/EngineShell_v0.1.apk EngineShell/app/build/outputs/apk/debug/app-debug.apk
```

`dist/EngineShell_v0.1.apk` 未删除，v0.2 为新增文件。
