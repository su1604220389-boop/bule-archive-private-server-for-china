# P0 修复记录：注入即闪退（进入碧蓝档案 1 秒崩溃）

时间：2026-11-11 16:0x ~ 16:13
设备：PLR110 / Android 17 / arm64-v8a / LSPosed
目标：com.RoamingStar.BlueArchive（国服）

## 一、现象

从启动器点「打开蔚蓝档案」→ 游戏进程起来约 1 秒即闪退（用户操作路径：选择进入方式 → 进入碧蓝档案 → 立刻闪退）。权限均已给足（LSPosed 启用 + 作用域勾选 + Root 授权），排除授权问题。

`LauncherActivity.launchGame()` 本身没问题：走 `getLaunchIntentForPackage()` + `FLAG_ACTIVITY_NEW_TASK`，系统解析到的入口是 `com.RoamingStar.BlueArchive/com.tech.core.TechSplashActivity`。闪退发生在游戏进程内、注入之后。

## 二、证据链

崩溃转储：`/data/tombstones/tombstone_16`（16:09:11）

```
Process name is com.RoamingStar.BlueArchive
pid: 30285, tid: 30285, name: tar.BlueArchive
signal 11 (SIGSEGV), code 2 (SEGV_ACCERR), fault addr 0x0000007fff7d7ff8 (write)
Process uptime: 1s
Cause: stack pointer is not in a rw map; likely due to stack overflow.
Abort message: 'JNI DETECTED ERROR IN APPLICATION: obj == null
    in call to GetLongField
    from ...HookBridge.invokeExactOriginalMethod(java.lang.reflect.Executable, java.lang.Object, java.lang.Object[])'
512 total frames
backtrace 中反复出现：[anon:dalvik-DEX data] (m.proceed+74) → (r0.callback+46) → (t.intercept+772)
```

三点闭环：

1. `Process uptime: 1s` —— 注入瞬间崩，不是玩到一半。
2. `Abort message` 的调用者是 LSPosed 框架自身的混淆类 `...HookBridge.invokeExactOriginalMethod`，参数类型正是 `java.lang.reflect.Executable`。
3. 512 帧全部是 `t.intercept → r0.callback → m.proceed` 的循环 —— hook 回调里又调回被 hook 的方法，无限递归，栈指针越界（SIGSEGV）。

## 三、根因

`HookLoad` 在 `handleLoadPackage()` 里、游戏进程刚起来时就调用了两个「反检测」类：

| 类 | hook 目标 | 后果 |
|---|---|---|
| `LSPosedBypass.init()` | `Throwable.getStackTrace`、`Thread.getStackTrace` | 框架写日志/抛异常必取堆栈，被自己的 hook 拦回 → 递归 |
| `ArtBypass.init()` | `java.lang.reflect.Executable.getModifiers` | 框架生成 hooker 必然反射读 `Executable` 字段，被 hook 拦回 → proceed 传 null this → `GetLongField obj == null` → JNI abort |

另外 `log()` 每条都调用 `XposedBridge.log()`，会走 LSPosed 日志通道（框架内部再取调用栈），既放大递归风险，也在游戏进程留下 xposed/lspd 痕迹。

## 四、修复内容（仅 Java 层，未动 jni/）

1. **整体删除** `LSPosedBypass` 与 `ArtBypass`（用户要求：确认无效就整体删掉，不留空开关）。理由：国服 BA 的反作弊是 native 线程扫描 + 完整性校验，不通过 Java 反射读 `getModifiers`，也不靠 Java `getStackTrace` 找 xposed，两个 hook 对检测零收益、对稳定性必崩。
2. 删除 `handleLoadPackage` 中对两者的调用。
3. `log()` 移除 `XposedBridge.log(...)`，只保留 `Log.i` + 写 `azusa_load.log`。

## 五、验证

- 构建：Gradle 8.7 + AGP 8.1.4，`assembleRelease` BUILD SUCCESSFUL（38 tasks，15s）。
- 产物：`AzusaBA_5.2.5_release.apk`，3,630,681 B，SHA-256 `f2266d58199a9ea7aca3eb4046fce84646155da70b5e2908efdcc6c3d78c1ee1`。
- 证书 SHA-256 `354d84daf3e1888b33a633eb2efdef37c080ea8cd86c1fdca555470db2c906d1`，与 `HookLoad.EXPECTED_SHA256` 一致（自校验不会误判篡改）。
- dex 内 `LSPosedBypass` / `ArtBypass` 命中数 0（确认已从产物移除）。
- 覆盖安装成功（`pm install -r -d` → Success，lastUpdateTime 16:12:55）。
- 实机启动验证（`am start -n com.RoamingStar.BlueArchive/com.tech.core.TechSplashActivity`）：进程 8929 持续存活 > 2 分钟，无新 tombstone（最新仍是修复前 16:09 的 tombstone_16）。
- 注入日志 `azusa_load.log`：

```
16:13:51.219  === Azusa 启动 ===
pkg=com.RoamingStar.BlueArchive pid=10264 sdk=37 64bit=true
16:13:51.222  音量键 Hook 已安装
16:13:51.223  onCreate Hook 已安装
```

native 侧 `azusa_native_log.txt`：配置路径已指向游戏 external files，`bridge bound: onInjected=0x... onToggle=0x...`，说明 so 加载与 bridge 绑定正常。

## 六、后续注意

- 任何「反检测」都不要 hook JVM/ART 核心方法（getStackTrace / getModifiers / Class.getDeclaredMethods / ClassLoader 相关）。这类 hook 会与 LSPosed 框架自身互相递归，必然栈溢出。
- 需要隐藏痕迹时，改走：LSPosed 作用域隐藏、不在游戏进程调 `XposedBridge.log`、native 侧符号与 maps 处理（详见 `audit/anti-detection.md`）。
