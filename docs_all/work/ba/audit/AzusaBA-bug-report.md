# AzusaBA 源码 Bug 审查报告（主报告 / Lead）

审查对象：`AzusaBA/`（LSPosed 模块 + native IL2CPP Hook + ImGui/GLES3 覆盖层，自称 5.2.5 / 游戏 3.0.2）
审查方式：全量静态阅读 + **真实编译验证**（NDK r27c sysroot + clang 18，arm64-v8a，`-fsyntax-only`）
说明：仓库自带的 `docs/ANALYSIS.md`（上一版缺陷）与 `docs/CHANGES.md`（声称已修）只作对照，不当结论。

---

## 0. 结论

**这份源码目前编译不过**（P0-1，已实测复现）。即使补上编译错误，仍存在 6 个必现级别的功能性缺陷，其中 2 个是本次「Alpha8 字体图集」改造直接引入的（图片全变白、切后台回来文字全丢），2 个是「按需出帧 / GL 上下文重建」改造引入的生命周期漏洞。

---

## P0 —— 阻断构建 / 必现功能损坏

### P0-1 `g_cfgPath` 在声明之前被使用 → 编译直接失败

- 位置：`main.cpp:2009`（使用） vs `main.cpp:2048`（定义）
- 现场：

```cpp
// main.cpp:2009，init_my_hook() 内
LOGW("功能仍按 %s 里的开关生效；需要面板请改用 LSPosed 加载",
     g_cfgPath[0] ? g_cfgPath : "(未设置配置路径)");
...
// main.cpp:2048，两万字节之后才是定义
static char g_cfgPath[512] = {0};
```

- 实测：

```
main.cpp:2009:14: error: use of undeclared identifier 'g_cfgPath'
main.cpp:2009:29: error: use of undeclared identifier 'g_cfgPath'
2 errors generated.
```

- 修法：把 `static char g_cfgPath[512] = {0};` 与 `static void ConfigPathSet(const char*)` 前置到 `init_my_hook()` 之前（或放到文件头部全局区）。**打上这个前置声明后，`main.cpp` 语法检查 0 error**，即这是唯一的编译级错误。

---

### P0-2 字体图集改 Alpha8 时把**唯一的** fragment shader 改成取 `.r` → 所有图片变白色剪影

- 位置：`ImGui/backends/imgui_impl_opengl3.cpp:719 / 729 / 741`（三处分片着色器）
- 现场：

```glsl
// 实际生效的 #version 300 es 那条（:741）
Out_Color = vec4(Frag_Color.rgb, Frag_Color.a * texture(Texture, Frag_UV.st).r);
```

- 根因：ImGui 的 OpenGL3 后端**只有一个 shader program**，字体图集和 `ImGui::Image` / `drawList->AddImage` 的 RGBA 图片**共用它**。改成 `.r` 后：
  - 字体：`tex.r = alpha`，正确；
  - 图片：tint 是白色 `(1,1,1,1)`，输出 RGB 恒为白，alpha 取图片**红色通道** → 背景图 / 浮动图标 / 头像 / 立绘 / 毛玻璃底图**全部变成白色剪影或不透明方块**。
- 影响面：`DrawBackgroundImage`、`DrawFloatingIcon`、头像与立绘、`BakeBlurFromSmall` 生成的所有贴图。等于整个 UI 的视觉资产报废，字体反而正常 —— 现象会非常迷惑。
- 正确修法（保持 Alpha8 省内存，同时不动 shader）：

```cpp
// 字体纹理上传后（imgui_impl_opengl3.cpp:573 之后），只对字体纹理做 swizzle：
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_R, GL_RED);
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_G, GL_RED);
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_B, GL_RED);
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_A, GL_RED);
// 然后把 :719 / :729 / :741 三处还原成：
//   vec4(Frag_Color.rgb, Frag_Color.a * texture(...).a)   // 或原版 Frag_Color * texture(...)
```

（`GL_TEXTURE_SWIZZLE_*` 是 GLES3 核心功能；本工程上下文是 3.0，可用。）

---

### P0-3 第二次 GL 上下文重建时字体纹理上传 `NULL` → 回到前台文字全消失

- 位置：`imgui_impl_opengl3.cpp:545-573` + `main.cpp:4317-4321` + `main.cpp:4354-4377`
- 链路：
  1. 首帧 `step()` 里 `ClearTexData()` 把字体图集 CPU 侧像素释放（`main.cpp:4317`）；
  2. 切后台/锁屏回来，`onSurfaceCreated` → `nativeOnContextRecreated()` → `CreateDeviceObjects()` → `CreateFontsTexture()`；
  3. `GetTexDataAsAlpha8()` 因为 `TexReady == true` **不会重新 Build**，返回 `pixels == NULL`；
  4. 代码没有判空，直接 `glTexImage2D(..., GL_RED, GL_UNSIGNED_BYTE, pixels=NULL)` → 分配一张内容未定义（实际全 0）的纹理 → **字体 alpha 全 0，所有文字不可见**。
- 修法：

```cpp
io.Fonts->GetTexDataAsAlpha8(&pixels, &width, &height);
if (!pixels) {
    // CPU 侧像素已被 ClearTexData 释放：重建图集
    io.Fonts->ClearInputData();      // 或重新 AddFontFromMemoryTTF
    io.Fonts->ClearTexData();
    // 最稳的做法：重新执行 Android_LoadFont() 的 AddFont... 流程后再取
    io.Fonts->GetTexDataAsAlpha8(&pixels, &width, &height);
    if (!pixels) return false;
}
```

更简单的工程做法：**不要 `ClearTexData()`**（14MB 换来上下文重建可用），或者在重建路径里重新加载字体（`Android_LoadFont()` 再跑一次）。

---

### P0-4 `imgui_Shutdown()` 不重建、不释放；`onDetachedFromWindow` 的 `queueEvent` 不保证执行

- 位置：`GLES3JNIView.java:115-130`、`main.cpp:4341-4349`、`main.cpp:4149-4193`
- 两个独立缺陷：
  1. `queueEvent()` 只是入队，紧接着 `super.onDetachedFromWindow()` 会让 `GLSurfaceView.GLThread` 走 `requestExitAndWait()`。退出路径上队列**可能不被 drain** → `imgui_Shutdown()` 不执行 → `g_Initialized` 仍为 `true` → 下次挂载 `init()` 直接 early-return（`main.cpp:4153`）→ 新 EGL 上下文里没有 shader/VBO/字体纹理 → **面板黑屏 / GL_INVALID_OPERATION**。
  2. `imgui_Shutdown()` 只 `DestroyContext`，**不 `glDeleteTextures` 掉 bg/icon/avatar/char/blur**（`g_bgTex` 等，最大 2048×2048 = 16MB）。每次 overlay 重建泄漏一批纹理。
- 修法：在 `onPause()` 里 `queueEvent` 一次 shutdown（`GLSurfaceView.onPause()` 保证 GL 线程当时还活着），或在 `init()` 里加"上下文代数"检测：EAGL 重建时强制 `DestroyDeviceObjects + CreateDeviceObjects + EnsureTextures`；`imgui_Shutdown()` 补 `glDeleteTextures`。

---

### P0-5 非 Unity 线程调用 `UILabel.set_text` / `UISlider.set_sliderValue`，且与主线程无锁共享数组

- 位置：`main.cpp:2019-2042`（`lobby_look_thread` 每 16ms → 500ms 调 `RefreshAllLevelLabels()`）、`main.cpp:788-804`、`main.cpp:726-737`
- 根因：
  - `lobby_look_thread` 是 `pthread_create` 出来的普通线程，只做了 `il2cpp_thread_attach`；它不是 Unity 主线程。Unity 的 UI 组件（UILabel/UISlider）**只能在主线程访问**，跨线程 `runtime_invoke` 会踩 Unity 的对象状态/GC 写屏障，表现为随机崩或界面错乱。
  - `g_lvOwners[]` 由游戏主线程的 `RegisterLevelOwner()` 写入，同一个数组又被 `lobby_look_thread` 遍历并**原地删除**（`g_lvOwners[i] = g_lvOwners[g_lvOwnerCount-1]; g_lvOwnerCount--;`）→ 无锁数据竞争，可能读到正在被替换的槽、计数错乱。
- 触发条件：面板打开「本地等级」后在大厅/结算场景切换（用户最容易做的操作）。
- 修法：把 `RefreshAllLevelLabels()` 改成在 Unity 主线程执行 —— 用一个被游戏每帧调用的 hook 里做（例如已有的 `SetLevelExp_Hook` / `SpineAnim_LateUpdate_Hook`），或 `Bridge.postToMain` → `doAction(WHAT_REFRESH_LEVEL)`（当前 `doAction` 是空 switch，见 P1-9）。`g_lvOwners` 加自旋锁或改成主线程独占 + 原子快照。

---

### P0-6 伤害被放大两次 → 开 10 倍实际约 100 倍

- 位置：`main.cpp:1296-1301`（`ApplyDamage_Hook` 直接乘 `damageResult+0x18`）与 `main.cpp:1468-1472`（`ApplyStatMods` 把 `DamageRatio(38)/AttackPower(2)` 乘同一倍率）
- 根因：属性表在伤害计算**之前**已经被乘过 `mult`，游戏算出的 `damageResult` 本身就是 `mult` 倍；hook 返回前再乘一次 → `mult²`。
- 附带问题：关掉功能时 `StatRestoreRecent()` 只能回写属性表，**已经结算的这次伤害回不来**；如果游戏侧有伤害上限/校验，倍率爆炸更容易被判定异常。
- 修法：二选一。推荐只用属性表通道（更平滑、可还原），把 `ApplyDamage_Hook` 的倍率分支删掉，只保留「我方受伤归零」；或者反过来，`ApplyStatMods` 不再改 38/2，只由 `ApplyDamage` 乘一次。

---

## P1 —— 功能错误 / 稳定性隐患

| 编号 | 位置 | 问题 | 修法 |
|---|---|---|---|
| P1-1 | `main.cpp:4256-4264` | 配置落盘 `save_config()`（open+write+**fsync**+rename）在 **GL 渲染线程**每 800ms 执行一次，fsync 会阻塞整帧 | 改成独立写盘线程 + 队列；或去掉 fsync（配置不是关键数据） |
| P1-2 | `main.cpp:1362-1374` | 属性缓存探测失败时「逐出最旧」并把**当前值**当原始值登记：如果当前值已经是乘过的值，就会二次放大（旧 `clear()` 的 bug 只是概率变低，没根除） | 逐出时不要登记新 orig（直接返回 false 不修改），或按 stat 对象生命周期整体失效 |
| P1-3 | `main.cpp:1615` | `RestorePlayerHp` 取不到 MaxHP 时 `target = 999999`，把 HP 写成远超上限的值 | 取不到就不写（`return`），宁可不锁血 |
| P1-4 | `main.cpp:4442-4445` vs `4662 / 4686` | `setBridge()` 里 `DeleteGlobalRef(g_bridge)` 之后立即置空，而 GL 线程可能正在用旧 ref 调 `CallVoidMethod` → use-after-free | 加互斥或改为「只绑一次、不重建」；至少不要在运行期反复 setBridge |
| P1-5 | `main.cpp:4702-4716` | `RegisterNatives` 表缺 `setRemoteNotice` / `setRemoteBg` 两项（Java 侧声明了 15 个，表里 13 个） | 补两行；否则只靠 `Java_com_kai_lobby_*` 符号兜底，一旦 `--gc-sections` 裁掉导出符号就 `UnsatisfiedLinkError` |
| P1-6 | `main.cpp:4522-4523` | `len != (jsize)(w*h*4)` 在 `w*h*4` 整型溢出时可被绕过 → `MakeTexture` 按错误的 w/h 读像素 → 堆越界读 | 用 `int64_t` 算：`if ((int64_t)w*h*4 != len || w > 8192 || h > 8192) return;` |
| P1-7 | `RemoteBg.java:89 / 100` | 仍对同一 `HttpURLConnection` **两次** `getInputStream()`（先量尺寸、再解码）。第二次响应体已被消费，`decodeStream` 很可能返回 `null` → 远程背景图**永远不生效**；即使生效也要下载两遍 | 先 `readAll` 成 `byte[]`，再对 `ByteArrayInputStream` 解码两次 |
| P1-8 | `MainActivity.java:45-59` + `HookLoad.java:292-322` | 音量键：`uiOpen` 在 `afterHookedMethod` 里取（此时 `ToggleUI()` 尚未执行），**面板关闭时按音量−会同时把系统音量降一格**（CHANGES 把它写成"设计"，但这是用户可感知的副作用）；且 `mp.setResult(true)` 在方法末尾对所有 action 生效，按住连发的 DOWN 都被吞 | 明确交互：只在 `ACTION_DOWN && repeatCount==0 && uiOpen` 时吞；面板关闭时不要动音量就改成 `return`（或短按吞、长按放行） |
| P1-9 | `main.cpp:4576-4583` + `Bridge.java:50` | `doAction()` 是空 `switch`，`Bridge.onToggle()` 是空方法 → `postToMain` / `onToggle` 整条链路是死代码 | 删掉，或把 P0-5 的等级刷新、公告重判等搬到 `doAction` 里真正实现 |
| P1-10 | `main.cpp:41-58` | 日志常驻 fd 的 `g_logFd` 生命周期无锁：并发 `if (fd<0) open` 会泄漏 fd；`setLogPath` 关 fd 的瞬间别的线程可能正 `write` → 写入被复用的 fd（串到别的文件） | `std::atomic<int>` + 关闭时先置 -1 再 close；或每线程独立 fd |
| P1-11 | `Game/Config.cpp:166-170` | 文本配置读缓冲固定 4096，超出部分**静默丢弃**（文件被截断后下次保存会覆盖掉被丢弃的字段）；`CfgToI` 不查 `errno` | 用 `fstat` 拿大小 + 动态缓冲；`strtoll` 后检查 `ERANGE` |
| P1-12 | `Game/Config.cpp:154-164` | 「兼容极老二进制格式」分支用 `st_size == sizeof(sConfig)` 判断：将来结构体缩小/文本文件恰好等长时会误判成二进制并 `unlink` | 加 magic 头（如首 8 字节 `AZUSABIN`）再判 |
| P1-13 | `main.cpp:4626-4628` / `4538-4560` | `ApplyPendingBg()` 每换一次背景图都 `DownsampleToSmall + BakeBlurFromSmall`（对 2048² 做 4M 像素遍历）在 GL 线程同步执行 → 掉帧 | Java 侧先 `inSampleSize` 到 ≤1024；或把模糊放到 Java/后台线程 |
| P1-14 | `main.cpp:352-387` | `UpdateCharacterList()` 在 GL 线程一帧内对几百个角色各做 2 次托管调用（`NameOf`/`DevOf`） → 打开面板瞬间卡顿几百 ms | 分帧构建（每帧 20 个）或放到 `lobby_look_thread`（只取字符串，不碰 UI 组件） |
| P1-15 | `main.cpp:1416-1431` | `StatRestoreRecent()` 在 GL 线程遍历 4096 槽并对游戏托管对象**写内存**（`StatWriteOrigForKey`），对象可能已被 Unity 销毁 → 野指针写 | 改为在 Unity 主线程（`doAction`）执行；写前只信任「最近一帧刚访问过」的槽 |

---

## P1-Java 层（补充）

### P0-7 `readAll()` 永远抛异常返回空串 → 自定义公告/背景 URL 永久失效

- 位置：`RemoteNotice.java:174-183`，被 `RemoteNotice.java:55` 与 `RemoteBg.java:41` 调用
- 现场：

```java
return readStream(in).substring(0, Math.min(cap, Integer.MAX_VALUE));   // cap=1024
```

- 根因：`readStream()` 返回的是**实际长度**（配置文件通常几十字节），`substring(0, 1024)` 直接 `StringIndexOutOfBoundsException` → 被外层 `catch (Throwable)` 吞掉 → 返回 `""`。
- 后果：`azusa_notice_url.txt` / `azusa_bg_url.txt` **永远不会生效**，公告与背景图永远走内置写死 URL —— 与注释里"URL 可以在不重新打包的情况下改"完全相反。
- 修法：`String s = readStream(in); return s.length() > cap ? s.substring(0, cap) : s;`

### P1-16 签名校验 5 条 fail-open 路径 + 期望值仍是 AOSP testkey

- 位置：`HookLoad.java:72-125`
- `MODULE_PATH == null` / `getPm() == null` / `pi == null` / `cert == null` / `catch` —— **全部 `return true`**；`EXPECTED_SHA256`（:55-56）是 AOSP testkey 证书哈希，人人可签。
- 结论：这段校验目前**没有任何防护作用**（重打包照样通过）。`CHANGES.md` 只改了 API 分支，没换证书。

### P1-17 运行模式写 4 个 `Android/data` 目录必然失败

- 位置：`LauncherActivity.java:433`
- Android 11+ 普通 app（含 targetSdk 26 的 legacy 模式）无法写**别的应用**的 `Android/data/<pkg>/files`；4 条写入全部失败，真正生效的只有 ContentProvider（`ModeProvider`）和自身 files。

### P1-18 日志实现开销

- `HookLoad.java:603-620`：`log()` 是 `synchronized`，每条都 `new FileOutputStream(sLogFile, true)` + `XposedBridge.log` → 高频 hook 场景（26 个 hook 全开）会放大成每秒上千次 open/close。

### P1-19 `GLES3JNIView.bridge` 被重复绑定

- `HookLoad.java:498` 赋值 + `GLES3JNIView.java:82-87` 每次 `onSurfaceCreated` 都 `setBridge(bridge)` → 触发 native `DeleteGlobalRef`（P1-4）。overlay 重建频繁时放大竞态窗口。

---

## P2 —— 隐患 / 可维护性

1. `main.cpp:1909` 的 `g_hookMask` 是函数内局部变量，`TRY_HOOK` 宏展开依赖它作用域正确 —— 现在能过，但任何人把宏挪出作用域就编译失败；建议提升为文件级 `static`。
2. `main.cpp:1889-1900` 安全模式路径硬编码 `com.RoamingStar.BlueArchive`（国服），日服/国际服/渠道服用 `azusa_safe.flag` 二分时全部失效；应遍历四个 `TARGET_PACKAGE_*`。
3. `main.cpp:1253-1258` `IsPlayerSide/IsEnemySide` 用 `==` 比较 `TacticEntityType`。该枚举是 `[Flags]`（`TT_Student=1, TT_Minion=2, TT_Elite=4...`）时，组合值会漏判 → 功能静默不生效。建议 `(t & TT_Student) != 0` 形式，或先打印实测值确认。
4. `main.cpp:1618` 锁血只在 `cur > 0 && cur < target` 时写；`cur == 0`（被一击打死）不会复活，这与"锁血"预期一致，但血条 UI 不刷新，容易被当成没生效。
5. `main.cpp:4354-4377` `nativeOnContextRecreated()` 在旧上下文已销毁后仍调 `ImGui_ImplOpenGL3_DestroyDeviceObjects()`（内部 `glDeleteTextures/glDeleteBuffers`）。在**新**上下文里这些名字可能属于别的对象 → 误删。应只把 `bd->FontTexture=0 / ShaderHandle=0...` 置空，不发 GL 删除。
6. `main.cpp:4149-4193` `init()` 里 `ImGui::GetStyle().ScaleAllSizes(2.2f)` 只在首次执行；分辨率变化（分屏/横竖屏）不会重算 → 布局错位。
7. `main.cpp:4573` 重复声明 `setRemoteNotice`（无害但说明该文件缺少统一头）。
8. `main.cpp:1714` `for (int i = 0; i < 60 && !Il2CppApiReady(); i++) usleep(500000);` 在 `init_my_hook()` 里**同步**等待最多 30 秒；它跑在 `main_thread`，不影响 UI，但 `MarkThisProcessHooked()` 已经置位环境变量 —— 若这 30 秒内又有一份 so 被 `System.load`，第二份会直接放弃（预期行为，但日志容易误判）。
9. `Assets/xposed_init`（`com.kai.lobby.HookLoad`）与 Manifest、`applicationId` 一致 ✅；`res/values/array.xml` 四个 scope 与 `TARGET_PACKAGE_*` 一致 ✅（这两处没问题，供核对）。
10. `build.gradle`：`ndkVersion '27.0.12077973'` 与本机/CI 的 r27c 不一致会触发下载；`compileSdk 33 / targetSdk 26` 与 SDK 36 设备混用，`-z max-page-size=16384` 已加（对），但 Java 侧仍依赖 targetSdk 26 的宽松存储。
11. 遗留死代码（不参与编译，但会误导后续维护）：`jni/Anti/*.h`（2,595 行）、`il2cppApi/il2cpp_dump.cpp`（731 行）、`ImGui/` 根目录两份 backend 副本、`Tools/PtrHook.cpp` + `HookUtils.cpp`（已从 Android.mk 移除但文件还在）。
12. `docs/patch/GLES3JNIView.java` 与实源码**签名已不一致**（docs 里是 `setRenderActive(GLSurfaceView, boolean)`，源码是 `setRenderActive(boolean)`）→ 文档按旧版写的，照抄会编译不过。

---

## 3. `docs/CHANGES.md` 声称 vs 代码实际

| CHANGES 声称 | 实际 |
|---|---|
| 配置持久化 `save_config` 落地 | ✅ 有了，但 `g_cfgPath` 编译错误（P0-1）让整条链根本编不出来；且落盘在 GL 线程 fsync（P1-1） |
| 属性缓存改固定槽位 + 自旋锁 + 逐出 | ✅ 结构在，但逐出仍会把乘过的值当原值（P1-2）、还原在 GL 线程写游戏对象（P1-15）、双通道重复放大（P0-6） |
| 字体图集改 Alpha8，预计 58MB→14MB | ⚠️ 内存确实降了，但**图片全变白剪影**（P0-2）；上下文重建后字体全丢（P0-3） |
| GL 上下文重建（P0-3） | ⚠️ 代码在，但重建路径用了 `pixels=NULL` 的字体（P0-3）、旧上下文误删（P2-5）、shutdown 不保证执行（P0-4） |
| 按需出帧省电 | ⚠️ 逻辑在，但 `doAction` 空实现导致"打开面板后需要一帧"的兜底只有 `requestRender` 一条路（P1-9），且 `g_uiOpen` 跨线程写（P0-8 类） |
| 音量键只吞"面板打开时" | ⚠️ 部分对，但 UP/长按仍被吞、关闭面板时会顺带调音量（P1-8） |
| 触摸矩形改推送 + 500ms 兜底 | ✅ 基本可用；但 `PushTouchRectIfChanged` 在 `setBridge` 里被当"补推"用，线程语义混乱（P2） |
| 签名校验改 `GET_SIGNING_CERTIFICATES` | ✅ API 分支在；`EXPECTED_SHA256` 仍是 AOSP testkey（CHANGES 自己承认） |
| `ModeProvider` 加 uid 白名单 | ✅ 已加（看 `ModeProvider.java:call()`） |
| `RemoteBg` 重复下载 | ❌ **没修**（P1-7） |
| `Anti/*` / dump / 重复 backend 清理 | ❌ 只是没编译，文件都在（P2-11） |

---

## 4. 编译验证证据

```
# 环境：NDK r27c sysroot + clang 18，target aarch64-linux-android26
clang++ --target=aarch64-linux-android26 --sysroot=$NDK/.../sysroot \
  -stdlib=libc++ -std=c++17 -fno-rtti -fno-exceptions -fsyntax-only main.cpp
→ main.cpp:2009:14: error: use of undeclared identifier 'g_cfgPath'   (x2)

# 在副本上补一行前置声明后：
→ 0 error（EXIT=0）
```

结论：**P0-1 是唯一的编译级错误**；其余全部是运行期/逻辑缺陷。

---

## 5. 建议修复顺序

1. **P0-1**（一行前置声明）→ 先让它能编。
2. **P0-3 + P0-2**（字体/图片）：这两条决定"进游戏能不能看"。
3. **P0-4**（GL 生命周期）：决定"切后台回来还活着吗"。
4. **P0-6**（双重放大）：决定"战斗数值会不会秒炸"。
5. **P0-5 + P1-15**（跨线程写 Unity 对象）：决定"开等级/关功能会不会随机崩"。
6. 其余 P1 按上表顺序。
