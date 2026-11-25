# AzusaBA 修复记录 — native 侧（Lead 主刀）

原始文件已备份：`audit/orig_backup/jni/`（main.cpp / Config.cpp / Config.h / imgui_impl_opengl3.cpp）。

编译验证环境：NDK r27c sysroot + clang 18，`--target=aarch64-linux-android26`，`-std=c++17 -fno-rtti -fno-exceptions`，`-fsyntax-only`。

---

## 一、`jni/main.cpp`（26 处标记 `[FIX ...]`）

| 编号 | 位置 | 修了什么 |
|---|---|---|
| P0-1 | 1744 / 2115 | `g_cfgPath` 定义前置到 `init_my_hook()` 之前（原来 2009 行用、2048 行才定义 → 编译失败） |
| P0-4 | 2352 / 4444 | 新增 `ReleaseUITextures()`：`imgui_Shutdown()` 里真正 `glDeleteTextures` 掉 bg/icon/avatar/char/blur（5 张），并清空模糊缓存；`g_blurSrcTex` 只是别名，不重复删 |
| P0-5 | 708 / 716 / 838 / 2105 | 等级标签刷新从 `lobby_look_thread`（非 Unity 线程）移到 `SpineAnim_LateUpdate_Hook`（Unity 主线程）执行的 `MainThreadTicks()`；look 线程不再碰 UILabel |
| P0-6 | 1349 | 删掉 `ApplyDamage_Hook` 里的 `*dmg *= mult`：倍率只由 `ApplyStatMods` 的属性表通道施加，消除 mult² |
| P0-7 | 2557 / 4375 | 新增 `g_uiReq` 请求队列 + `ApplyUIRequest()`：音量键在 Java UI 线程只投递请求，`g_uiOpen/g_island` 只在 GL 线程（step）里改 |
| P0-8 | 4639 | `setRemoteBg` 用 `int64_t` 算 `w*h*4` + 8192 上限，防 int 溢出绕过长度校验 |
| P1-2 | 1412 | `StatGetOrig` 探测失败不再「逐出最旧并登记当前值」，直接放弃本次改写（防 mult^n 复利） |
| P1-3 | 1659 | `RestorePlayerHp` 取不到 MaxHP 就 return（删掉 999999 兜底） |
| P1-4 | 4556 | `setBridge` 不再 `DeleteGlobalRef` 旧 ref，且同对象重复绑定直接返回（消除跨线程 UAF） |
| P1-5 | 4846 | `RegisterNatives` 补齐 `setRemoteNotice` / `setRemoteBg`（13 → 15） |
| P1-9 | 4695 | `doAction()` 不再是空 switch：实现「刷新等级标签」「还原战斗属性」两个主线程动作 |
| P1-10 | 43 / 67 | 日志 fd 改原子取用/关闭（CAS open + exchange close），消除 fd 泄漏与串写 |
| P1-14 | 374 | `UpdateCharacterList()` 改分帧：每帧最多 24 个角色，避免打开面板瞬间卡几百 ms |
| P1-15 | 4364 / 838 | 属性还原不再在 GL 线程写游戏对象，改为置 `g_statRestoreReq`，由 Unity 主线程执行 |
| P2-2 | 1945 / 1970 | `azusa_safe.flag` / `azusa_hookmask.txt` 遍历四个目标包名（原来只认国服） |
| P2-3 | 1298 / 1303 | `IsPlayerSide` / `IsEnemySide` 改位判断（`[Flags]` 组合值不再漏判） |
| 附加 | 4473 | `nativeOnContextRecreated`：检测 `g_fontDataFreed` → `Fonts->Clear()` + 重新 `Android_LoadFont()`，避免用 `pixels==NULL` 重建字体 |
| 附加 | — | 渲染模式缓存改文件级 `g_renderModeLast` + `ResetRenderModeCache()`，`init()` 与上下文重建后各复位一次（防卡在 WHEN_DIRTY） |

## 二、`jni/ImGui/backends/imgui_impl_opengl3.cpp`（4 处）

| 编号 | 位置 | 修了什么 |
|---|---|---|
| P0-3 | 548 | `CreateFontsTexture()` 增加 `pixels == NULL` 判空：宁可不上传，也不把全 0 纹理当字体 |
| P0-2 | 583 | 只给**字体纹理**设置 `GL_TEXTURE_SWIZZLE_R/G/B/A = GL_RED`（含 ES2 头缺失枚举的 `#ifndef` 兜底），保持 R8 省内存 |
| P0-2 | 745 / 768 | 三处 fragment shader 还原成 `Frag_Color * texture(...)`：图片（RGBA）与字体（swizzle 后等效 RGBA）共用同一 shader 不再互相污染 |

## 三、编译验证

```
# main.cpp（原始状态）
main.cpp:2009:14: error: use of undeclared identifier 'g_cfgPath'
# main.cpp（修复后）
EXIT=0
# imgui_impl_opengl3.cpp
BACKEND_RC=0（仅 IMGUI_IMPL_OPENGL_ES2 宏重复定义警告，头文件自动检测所致）
```

## 四、没有改的（需要你决策/需要真机验证）

1. **签名校验 fail-open + AOSP testkey**（`HookLoad.java:55-125`）：换成你自己的 release 证书哈希才有意义；我不知道你的证书 SHA-256，强行开启会把模块自锁在"拒绝注入"。
2. **`targetSdk 26` / `WRITE_EXTERNAL_STORAGE`** 这套宽松存储路线：升级 targetSdk 会连带影响 `azusa_*.txt` 全部路径，属于架构决策。
3. **`ScaleAllSizes(2.2f)` 不随分辨率重算**：改成按高度比例会让现有 UI 尺寸整体变化（视觉回归），留给你先看真机效果再决定。
4. **`nativeOnContextRecreated` 里仍调用 `DestroyDeviceObjects()`**：旧上下文已失效时这些纹理名理论上可能撞上新上下文的对象，但当前是在 `onSurfaceCreated` 第一步调用（新上下文还没分配资源），风险很低，改动收益不抵风险。
5. **`assets/libNeko_linker.so` / `Anti/*.h` / `il2cpp_dump.cpp` / ImGui 根目录重复 backend**：只是没参与编译，删不删由你决定。
