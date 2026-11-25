# 数美 4 个 Xposed 枚举方法：调用方核查（DEX 级，静态）

> 结论先给：**4 个方法全部有真实调用方**，共 5 处 `invoke-static`，调用方全在数美内部（3 个类）；结果最终进 JSON 上报。**不是死代码**。
> 取证：手写 DEX 解析（method_ids + 全 class_def 的 invoke 指令扫描，classes.dex / classes2.dex 都扫）；jadx 源码仅作辅证。未运行游戏。

## 1. 方法定义（classes2.dex；jadx `audit/ba-apk/jadx/sources/com/ishumei/smantifraud/l111l11111I1l/l1111l111111Il.java`）

| 方法 | 行 | 原型 | method_id | 做什么 |
|---|---|---|---|---|
| `l111l11111I1l` | 305 | `static boolean` | 11437 | `XposedBridge.jar` 文件存在性 |
| `l111l11111Il` | 313 | `static Set<Object>` | 11438 | 读 `XposedHelpers.fieldCache/methodCache/constructorCache` |
| `l111l1111l1Il` | 344 | `static Map<String,Object>` | 11440 | XposedBridge 字段 / `XposedInit.loadedModules` 等 |
| `l11l111l11Il` | 686 | `static boolean` | 11452 | `com.elderdrivers.riru.edxp.config.EdXpConfigGlobal`（EdXposed） |

宿主类：`Lcom/ishumei/smantifraud/l111l11111I1l/l1111l111111Il;`

## 2. 调用方（5 处 invoke-static，code_off 可复核）

| 被调 | 调用方 类#方法 | code_off | insns |
|---|---|---|---|
| `l111l1111l1Il()` | `…l1111l111111Il/l1111l111111Il$1;#run` | 0x62cb7c | 802 |
| `l111l11111Il()` | `…l1111l111111Il/l1111l111111Il$1;#run` | 0x62cb7c | 802 |
| `l111l11111I1l()` | `…l1111l111111Il/l1111l111111Il;#l1111l111111Il` | 0x62fc24 | 2173 |
| `l11l111l11Il()` | `…l1111l111111Il/l1111l111111Il;#l1111l111111Il` | 0x62fc24 | 2173 |
| `l111l11111I1l()` | `…l1111l111111Il/l11l1111I1l;#l1111l111111Il` | 0x6346e0 | 199 |

- `$1` = 匿名 `Runnable` → **后台线程采集**，非主线程。
- 2173 条指令的聚合器方法 `#l1111l111111Il(Map)Map` 内还做：`android.os.Debug#isDebuggerConnected()`、`Context#getFilesDir()`、系统属性、`SystemClock#elapsedRealtime()`。
- 结果去向：`LMapUtilsKt;#mapToJsonObject(Map)Lorg/json/JSONObject;` → 数美上报体。该方法常量池实测含键 `"hookJava"`、`"oaid"`、`"bssid"`、`"ssid"`、`"1:"`…`"6:"` → **Xposed/EdXposed 结果确实进入上报 JSON**（`hookJava` 极可能就是该键，字符串层面证据）。
- 另：`l11l1111I1l#l1111l111111Il` 结尾调用 `l11l1111I11l#l1111l111111Il()Lorg/json/JSONObject;` —— 设备信息持有者，同一份 JSON 装配链。

**重要坑**：jadx **没有**解出这两个调用方类（`…/l1111l111111Il/l1111l111111Il.java` 与其 `$1` 都不存在文件）。只看 jadx 会得出"无调用方"的错误结论 —— 本次结论来自 DEX 指令级扫描。

## 3. 数美在这包里到底跑不跑（入口）

| 证据 | 位置 | 结论 |
|---|---|---|
| `Lcom/airi/udata/component/SMComponent;` → `SmAntiFraud#create / getSDKVersion / registerServerIdCallback` | classes.dex（3 处 invoke） | 发行 SDK **已把数美接进来了**（确证） |
| `SmAntiFraud` 其余调用方 | classes2.dex：`SmAntiFraud$1`、`…l1111l111111Il/l1111l111111Il#getDeviceId` | 数美内部自调（确证） |
| `SMComponent` 源码 | jadx 未反编译 | `create` 是否被 `SDKConfigSettings.json` 门控：**未验证（推断默认开）** |

## 4. 我们会不会中 / 动不动

| 项 | 结论 |
|---|---|
| 我们 hook 数美方法吗 | 不。`grep -r ishumei AzusaBA/app/src` = 0 命中 → 不会产生"返回值不合理"特征 |
| 我们会被 `l111l11111Il()`（三 cache）看到吗 | **可能**。`XposedHelpers.findAndHookMethod`（`HookLoad.java:248/278/284`）经 `findMethodExact→getDeclaredMethod`，理论上不写 cache；需实测（打印 `methodCache.size()` 前后） |
| 我们会被 `l111l1111l1Il()` 看到吗 | **会**。任何 `XposedBridge.hookMethod` 都写 `XposedBridge.sHookedMethodCallbacks`；`XposedInit.loadedModules/loadedPackagesInProcess` 由 LSPosed 框架写，模块侧改不掉 |
| 处理建议 | 不动数美（改返回值=主动制造异常特征，收益≈0）。若要降特征：把上述 3 处 `findAndHookMethod` 换成 `XposedBridge.hookMethod(反射拿 Member)`，成本低，先测试机验 `methodCache` 是否真有变化 |
