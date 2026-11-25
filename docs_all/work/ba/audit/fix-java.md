# AzusaBA Java 层修复报告（java-fixer）

审查/修改对象：`AzusaBA/app/src/main/java/com/kai/lobby/*.java`
依据：`audit/AzusaBA-bug-report.md` 的 P0-7 / P1-7 / P0-4 / P1-4 / P1-19 / P1-8 / P1-18 / P1-17
约束遵守情况：**只改 Java 层**，`jni/` 零修改（本组三人只读 main.cpp 查证），未改 `AndroidManifest.xml`、未改 `targetSdk/minSdk`、未引入任何新依赖。

---

## 1. 修复清单

| # | 文件:行（修复后行号） | 原问题 | 现在的行为 |
|---|---|---|---|
| 1 | `RemoteNotice.java:176-190`（`readAll`） | `substring(0, Math.min(cap, Integer.MAX_VALUE))` 对实际长度只有几十字节的文件必定抛 `StringIndexOutOfBoundsException`，异常被 `catch (Throwable)` 吞掉 → **永远返回 `""`**，`azusa_notice_url.txt` / `azusa_bg_url.txt` 形同不存在 | 先 `String s = readStream(in)`，再 `s.length() > cap ? s.substring(0, cap) : s`；短文件原样返回 |
| 2 | `RemoteBg.java:91-121` + 新增 `readBody():169-192` | 同一个 `HttpURLConnection` 两次 `getInputStream()`：HTTP 响应体不可重放，第二次流已消费 → `decodeStream` 返回 null → **远程背景图永不生效**，且要下载两遍 | `readBody()` 一次读成 `byte[]`（上限 `MAX_BYTES = 4MB`，超限/异常返回 null → 走原失败日志），再用两个 `ByteArrayInputStream` 分别做 `inJustDecodeBounds` 与带 `inSampleSize` 的解码（`MAX_DIM=2048` 语义不变） |
| 3 | `GLES3JNIView.java:133-176`（`onPause` / `onDetachedFromWindow` / `postShutdownOnce`）+ `:116-129`（`onDrawFrame` 补 init） | 只在 `onDetachedFromWindow` 里 `queueEvent(imgui_Shutdown)`，紧接着 `super.onDetachedFromWindow()` 让 GLThread 走 `requestExitAndWait()`，队列**可能不被 drain** → `imgui_Shutdown` 不执行 → `g_Initialized` 仍为 true → 下次 `init()` 早退 → 新上下文里没有 shader/VBO/字体纹理（面板黑屏） | `onPause()` **先** `postShutdownOnce()` 再 `super.onPause()`（此时 GL 线程还活着）；`onDetachedFromWindow` 再投一次兜底；两者共用 `static volatile boolean sImguiShutdown` 幂等，真正只投递一次。补 `onResume` → 置 `sNeedReinit`，由 `onDrawFrame`（EGLSurface 必然有效的时刻）执行 `init()` 并把标记复位 |
| 4 | `GLES3JNIView.java:88-101`（`onSurfaceCreated`） | 每次 `onSurfaceCreated` 都 `setBridge(bridge)` → native `setBridge` 内部先 `DeleteGlobalRef(g_bridge)`，与正在回调的 GL/Unity 线程竞态（use-after-free、回调丢失） | `static volatile boolean sBridgeBound`，只在未绑定时绑一次（绑定成功才置位），`onDetachedFromWindow` 复位为 false 允许下次重新绑定 |
| 5 | `HookLoad.java:278-354`（`VolumeHook`） | ① `uiOpen` 在 `ToggleUI()` **之后**才判（其实写在切换前但结果用于切换后），关面板那一按既关面板又降一格系统音量；② `mp.setResult(true)` 在方法末尾对**所有 action** 生效，长按连发 DOWN / UP 全被吞 | `ACTION_UP` 分支只做收尾：`sSwallowUp` 置位则吞掉配对的 UP 并清位，然后 return；只有 `ACTION_DOWN && getRepeatCount()==0` 才处理；进入分支后先取 `uiOpen`（**切换前**状态）——为 true 时吞本次 DOWN（`sSwallowUp=true`）**并照常执行 ToggleUI**（开着就关），为 false 时不吞、只切到打开；`repeatCount>0` 一律不吞不切换 |
| 6 | `MainActivity.java:74-105`（`onWindowRect`） | native 从任意线程回调进来直接改 `LayoutParams` + `setLayoutParams` → `CalledFromWrongThreadException` / 布局错乱 | 懒初始化 `sMain`；把「比较 + 赋值 + `setLayoutParams`」整体放进 `Runnable`，**已在主线程则直接执行，否则 `sMain.post`**；进主线程后重新判 `sAttached` 与 `lp/touch` 非空（post 期间可能已 detach） |
| 7 | `HookLoad.java:633-668`（`log` / `flush` / 新增 `setLogFile`） | `flush()` 每条日志 `new FileOutputStream(sLogFile, true)` + `close()`，26 个 hook 全开时每秒上千次 open/close，把游戏线程 IO 拖死 | 持有 `static FileOutputStream sLogFos`（append），写入后 `flush()`，不再每条开关；写失败（存储卸载/空间满/流失效）才关流并置空，下一条自动重开；新增 `setLogFile(File)` 统一换文件（关旧流 → 记新文件），`handleLoadPackage` 里的 `sLogFile = null/f` 全部改为调用它；`XposedBridge.log` 保留 |
| 8 | `LauncherActivity.java:386-430`（`saveMode`，删 `:424-448` 老循环） | 往 4 个游戏的 `/sdcard/Android/data/<pkg>/files/azusa_mode.txt` 写入：Android 11+ 普通应用无权写别的 uid 的私有目录，4 条全部失败，只往 `why` 里塞异常名，误导排查 | 整段循环与 `gameOk` 变量删除（已确认无其它引用），注释改写为事实：真正生效的是 `ModeProvider`(ContentProvider)/prefs + 本 APP 自己的 `files/azusa_mode.txt`，`/sdcard/Azusa/mode.txt` 保留为公共目录兜底 |
| 9 | `RemoteNotice.java:30-36`（连带，**编译级**） | `/** 内置公告地址（` 这段 javadoc **没有结束符 `*/`** → 后面的 `DEFAULT_URL` 等字段全被吞进注释，`javac` 报 `unclosed comment` + 一串 `cannot find symbol`，**Java 层根本编译不过** | 补 `*/` 并写清「只有 `override=1` 才允许外部覆写」 |
| 10 | `Bridge.java:121-135`（连带，**编译级**） | `onWindowRectChanged(..., final int h)` 里又写 `final Handler h = ...`，与参数 `int h` 重名 → `error: variable h is already defined` + `error: incompatible types: Handler cannot be converted to int` | 局部 Handler 改名 `hd` |

> 第 9、10 项不在最初 8 条清单里，是**实测基线编译**（见第 4 节）暴露出来的真实编译级错误，不修则无法完成「javac 全绿」验收，故一并修掉。

---

## 2. 逐条补充说明

### 2.1 RemoteNotice / RemoteBg（远程内容落地）
- 两个类都跑在游戏进程里（LSPosed 注入），走游戏自己的 INTERNET 权限；`readAll` 是唯一的跨类配置读取入口（`RemoteBg:41` 也调它），所以 P0-7 一修，公告 URL 与背景图 URL 的外部覆盖同时恢复。
- `RemoteBg.readBody` 的超限判断在 **写入前** 做（`bos.size() + n > MAX_BYTES` 直接返回 null），避免先吃满 4MB 再判断。
- 解码两次都用**新的** `ByteArrayInputStream`（`decodeStream` 会消费流），这是本条 bug 的正解；没有再依赖 `conn.getInputStream()`。

### 2.2 GLES3JNIView 生命周期（P0-4 + P1-4/P1-19）
- 顺序严格是：`onPause()` 里 **先** `queueEvent` 再 `super.onPause()`。GLSurfaceView 的 `onPause()` 会暂停 GL 线程，反过来写就会丢掉这次 shutdown。
- `onResume` 不直接 `queueEvent(init())`，而是置 `sNeedReinit` 由 `onDrawFrame` 消费：`queueEvent` 只保证「在 GL 线程」，不保证「EGLSurface 还有效」；在 `onDrawFrame` 里调 `init()` 一定处于「上下文 + surface 都可用」的时刻，避免创建 shader/VBO 时状态未定义。
- `onSurfaceCreated` 里补了 `sImguiShutdown = false;`：`sImguiShutdown` 是 static，跨实例残留会让**新挂载的 overlay 第一次 onPause 跳过 shutdown**（每次重挂漏一次 ImGui 销毁）。新实例是新 GLThread/新队列，旧实例待执行的 shutdown 不会跑回来删掉新上下文。
- `sBridgeBound` 在 `onDetachedFromWindow` 复位，避免「detach 之后新实例永远绑不上 bridge」（与 `MainActivity.onOverlayDetached()` 复位 `sAttached` 同一类问题）。

### 2.3 音量键（P1-8）
三条路径收敛为：
1. `ACTION_UP`：只看 `sSwallowUp`，置位则吞本次 UP 并清位（保证 DOWN 吞了 UP 也吞，系统不会补一次音量动作）；
2. `ACTION_DOWN && repeatCount == 0`：
   - `uiOpen == true`（**切换前**状态）：吞本次 DOWN（`setResult(true)`）+ `sSwallowUp = true`，**然后照常 `ToggleUI()`**（这就是「按一下关面板」），不改系统音量；
   - `uiOpen == false`：不吞，执行「首次挂载 800ms 后开面板」或「直接 ToggleUI + requestOneFrame」；
3. 其余（`repeatCount > 0` 的长按连发、`ACTION_MULTIPLE` 等）：一律不吞、不切换。

> 中间发现并修正过一次回退：第一版把 `uiOpen == true` 写成「吞键 + return」，等于面板打开后再也关不掉。已按上面的语义改回「吞键 + 仍然切换」。

### 2.4 日志（P1-18）
- `log()` 仍是 `synchronized`，`flush()`/`setLogFile()` 也是 `synchronized`（同一把类锁），流对象不需要额外同步。
- 流在 `setLogFile()` 里重建；`handleLoadPackage` 选目录时先 `setLogFile(null)`（关掉上一次可能残留的流），`probe` 成功后 `setLogFile(f)`。
- 失败自愈：`write/flush` 抛异常 → `close()` + 置 null，下一条日志重新 `open`，不会因为一次 IO 错误永久丢掉日志。

---

## 3. native 侧依据（只读核对，未修改 jni/）

`AzusaBA/app/src/main/jni/main.cpp`（行号为本次快照，该文件正被其他成员修改，可能漂移）：

| 位置 | 内容 | 结论 |
|---|---|---|
| `:127` | `bool g_Initialized = false;` | 全局初始化标志 |
| `:4246` / `:4274` | `init()` 内 `if (g_Initialized) return;` … `g_Initialized = true;` | `init()` 本身幂等 → 重复调用安全 |
| `:4372` | `if (!g_Initialized || !g_renderReady) return;`（step/RenderOverlay） | shutdown 后 `step()` 永久早退 → **必须在回前台补 init**，否则黑屏 |
| `:4442` / `:4449` | `imgui_Shutdown()` 内 `g_Initialized = false;` | 印证「只 shutdown 不重建 = 面板死」 |
| `:4551` | `setBridge()` 内 `env->DeleteGlobalRef(g_bridge); g_bridge = nullptr;` | 印证 P1-4：运行期反复 `setBridge` 会与回调线程竞态 → 「只绑一次」是正解 |

---

## 4. 语法自检（命令 + 真实输出）

环境：PRoot Ubuntu，`javac 17.0.20.1`（`-source/-target 8`），`android.jar = /root/Android/platforms/android-35/android.jar`，
xposed 桩 jar 实际路径是 `AzusaBA/app/libs/xposed-api-82_compileonly.jar`（任务书里写的 `app/src/main/libs/` 不存在）。

### 4.1 基线（未修改的原始快照 `audit/orig_backup/java/`）—— 15 error

```
cd /data/user/0/com.ai.assistance.operit/files/workspace/9dc0fd0c-7cad-4366-8d0b-bad7165d8587
javac -source 8 -target 8 \
  -bootclasspath /root/Android/platforms/android-35/android.jar \
  -cp AzusaBA/app/libs/xposed-api-82_compileonly.jar \
  -d /tmp/jout-base audit/orig_backup/java/*.java

audit/orig_backup/java/Bridge.java:123: error: variable h is already defined in method onWindowRectChanged(int,int,int,int)
        final Handler h = sMain != null ? sMain : new Handler(Looper.getMainLooper());
                      ^
audit/orig_backup/java/Bridge.java:128: error: incompatible types: Handler cannot be converted to int
                    MainActivity.onWindowRect(x, y, w, h);
                                                       ^
audit/orig_backup/java/RemoteNotice.java:76: error: cannot find symbol
        return DEFAULT_URL;
               ^
  symbol:   variable DEFAULT_URL
...（RemoteNotice 连锁 cannot find symbol，共 13 条）
=== 统计：error 总数 = 15（RemoteNotice 13 + Bridge 2）
```

### 4.2 修复后（真实源码）—— 0 error

```
cd /data/user/0/com.ai.assistance.operit/files/workspace/9dc0fd0c-7cad-4366-8d0b-bad7165d8587/AzusaBA
rm -rf /tmp/jout && mkdir -p /tmp/jout
javac -source 8 -target 8 \
  -bootclasspath /root/Android/platforms/android-35/android.jar \
  -cp app/libs/xposed-api-82_compileonly.jar \
  -d /tmp/jout $(ls app/src/main/java/com/kai/lobby/*.java)

Note: app/src/main/java/com/kai/lobby/HookLoad.java uses or overrides a deprecated API.
Note: Recompile with -Xlint:deprecation for details.
=== EXIT=0
```

只保留两条 `deprecated API` 提示（`GET_SIGNATURES` 分支等原有代码，非本次引入），无 error/warning。
产物 `/tmp/jout/com/kai/lobby/` 下 8 个顶层 class + 匿名内部类全部生成（`Bridge.class`、`GLES3JNIView.class`、`HookLoad.class`(`HookLoad$VolumeHook.class` 等)、`LauncherActivity.class`、`MainActivity.class`、`ModeProvider.class`、`RemoteBg.class`、`RemoteNotice.class`）。

---

## 5. 残留风险 / 明确未做的事

1. **面板关闭时按音量− 仍会顺带降一格系统音量**：本次规格是「只吞面板打开时的按键」，不开面板那一下仍交给系统（否则等于永久劫持音量键，用户调不了音量）。若要完全无副作用，需改成「短按吞、长按放行」，代价是首次长按会漏一格且响应变慢 —— 属产品取舍，未擅自改。
2. `onResume` 的补 `init()` 依赖 `onDrawFrame` 至少再跑一帧。`RENDERMODE_WHEN_DIRTY` 且长时间无 `requestOneFrame`/触摸时，面板恢复会等到下一次请求帧；native `init()` 幂等，因此只是延迟、不会错乱。
3. **签名校验（P1-16）未动**：`EXPECTED_SHA256` 仍是 AOSP testkey、5 条 fail-open 路径保持原样。修它必须重新签 APK/换证书指纹，会改变交付包签名，超出「只修 Java 逻辑、不改交付形态」范围，建议由 lead 单独决策。
4. `sLogFos` 进程级常开、进程退出前不 close（无进程退出钩子）；被系统杀进程时由内核回收 fd，可接受。
5. `jni/` 下所有问题（P0-1/2/3/5/6、P1-1~P1-15 等）不在本组范围，由 native 侧成员处理。

---

## 6. 协作与写域记录

| 成员 | 任务 | 写域（互不重叠） |
|---|---|---|
| `java-net-fixer` | task-1 | `RemoteNotice.java`、`RemoteBg.java`、`LauncherActivity.java` |
| `java-lifecycle-fixer` | task-2 | `GLES3JNIView.java`、`MainActivity.java`、`HookLoad.java` |
| （跨写域追加，未署名） | Bridge 编译修复（P0-9） | `Bridge.java`：`final Handler h` → `hd`。task-2 原报告明确写「未动 Bridge」并上报了该编译错误，本修复在其报告之后落地，故单列一行，避免归因错位。 |
| `java-fixer`（本报告） | 复核 + 追加修复 + 全量验收 | `GLES3JNIView.onSurfaceCreated` 的 `sImguiShutdown = false;`（:104-106）、`audit/fix-java.md` |

复核结论：3 处复核意见已落地 —— ① `GLES3JNIView` 跨实例的 `sImguiShutdown` 复位；② `VolumeHook` 的「吞键但必须仍然切换」；③ 编译级 `Bridge.java` 局部变量重名。

---

## 7. 验收快照（javac 全绿终态）

```
=== EXIT=0    # 40 个 .class（8 个顶层类 + 匿名/内部类）
5fcd81fd0b7f5e91ebac03415f2cb437  Bridge.java
fd3966f798ff50209daa19ff3ebce075  GLES3JNIView.java
344015329321d9274e567e3db4d3fa08  HookLoad.java
596e539486923bcd0eca5e73630d39c7  LauncherActivity.java
fb852f2cfdcdaa354e87e596106f8fdb  MainActivity.java
4aa63df5c8e7c7ec5b5f06c35f74d98c  ModeProvider.java（未改）
e2777e4091ee1ef67b43031e9019ff73  RemoteBg.java
b89979d22120978d6e3f4e52d62c79c0  RemoteNotice.java
```

`ModeProvider.java` 哈希保持不变（本次未改），可作为「写域没有外溢」的旁证。
（原始基线快照在 `audit/orig_backup/java/`，可随时 `diff -u` 复核每一处改动。）

### 7.1 2026-11-11 复测（java-fixer 本人实测，不引用他人结论）

```
cd /data/user/0/com.ai.assistance.operit/files/workspace/9dc0fd0c-7cad-4366-8d0b-bad7165d8587/AzusaBA
rm -rf /tmp/jout-final-verify && mkdir -p /tmp/jout-final-verify
/usr/lib/jvm/java-17-openjdk-arm64/bin/javac -source 8 -target 8 \
  -bootclasspath /root/Android/platforms/android-35/android.jar \
  -cp app/libs/xposed-api-82_compileonly.jar \
  -d /tmp/jout-final-verify app/src/main/java/com/kai/lobby/*.java
Note: .../HookLoad.java uses or overrides a deprecated API.
=== EXIT=0
=== CLASS_COUNT 40
```

- 与 `audit/orig_backup/java/` 逐文件比对：仅 `ModeProvider.java` 字节完全相同（未触碰）；其余 7 个改动量（unified diff）为 Bridge +5/-2、GLES3JNIView +56/-7、HookLoad +87/-43、LauncherActivity +10/-30、MainActivity +27/-11、RemoteBg +46/-8、RemoteNotice +10/-4。
- **勘误**：本文件旧版 §7 记录的 8 个 md5 与工作区实际文件不符（是记录错误，不是源码又被改动：连未触碰的 ModeProvider 也对不上），已按本轮实测重置。以上表 + `javac` 输出为最终口径。

---

## 8. 仍需拍板的行为项（不阻塞本次 Java 交付）

1. **面板关闭时按音量− 的语义**（P1-8 剩余分歧）
   - 现状：面板关闭 → 唤起面板 **且** 系统音量降一格（`docs/CHANGES.md:135` 把它写成预期，`docs/ANALYSIS.md` P1-3 也要求「图标态正常调音量」）。
   - 但 `docs/ANALYSIS.md:512` 验收项 8 与 `audit/AzusaBA-bug-report.md` P1-8 要求「只唤起、不动音量」。三处文档互相冲突。
   - 选项：**A** 保持现状（任何状态都能调音量）；**B** 短按全吞（只切面板、音量永不改，代价是模块生效期音量− 无法调音量）；**C** 短按吞（切面板、不动音量）+ 长按放行（系统调音量）。C 同时满足两边意图，但需真机确认系统会接受「没有初始 DOWN 的 repeat DOWN」并调音量。
   - 建议：C；真机长按无效则回退 A。改动点仅 `HookLoad.VolumeHook`（约 10 行），需用户拍板后再动。
2. **`GLES3JNIView.onPause()/onResume()` 目前没有调用方**
   - overlay 由 `MainActivity.attach()` 里 `new GLES3JNIView(ctx)` + `addView` 挂到游戏 content view，宿主 Activity 不会把生命周期转发给这个 View；全 `lobby/*.java` 除本类外无 `.onPause()/.onResume()` 调用（grep 实测）。
   - 因此「暂停时 shutdown」当前是防御性死代码；真正投递只剩 `onDetachedFromWindow` 一次，且可能被 `GLSurfaceView.requestExitAndWait()` 丢弃。
   - 影响有限：`onSurfaceCreated` 的两条自愈路径能兜住（① shutdown 没跑成 → `g_Initialized` 仍 true → `nativeOnContextRecreated()` 重建 shader/VBO/纹理；② 跑成了 → `init()` 重建），不会留下「已初始化但无 GL 资源」的黑屏态。
   - 若要真正在暂停时释放 ImGui：需在宿主 `UnityPlayerActivity.onPause/onResume` 转调 `sCurrent.onPause()/onResume()`（跨文件、首次真正走 shutdown→init，有回前台首帧风险），建议作为独立任务并交用户真机验收。
3. **P1-16 签名校验**（AOSP testkey + 5 条 fail-open）未动：见 §5.3，需 lead/用户决策是否换证书重签（会改变交付包签名）。
