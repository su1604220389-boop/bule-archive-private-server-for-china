# BA 国服（com.RoamingStar.BlueArchive）Java/dex 层只读调查报告

- 负责人：ba-java-survey（只读分析，未改任何源码、未安装/启动游戏、未联网、未复制/解压 base.apk）
- 产物：本文件（`audit/ba-java.md`）
- 目标构建：`audit/ba-apk/classes.dex`（9,327,708 B）+ `classes2.dex`（10,158,904 B），仅 arm64-v8a

---

## 0. 方法与产物局限（重要，先看这段）

**现成 jadx 产物只覆盖约 20% 的类**：`jadx/sources` 有 3255 个 `.java`，而两个 dex 实际有 **15912** 个 class_def。关键类（`com.unity3d.player.UnityPlayer`、`UnityPlayerActivity`、`com.tech.sdk.bridge.*`、`AceApplication` 之外的部分、`EmulatorCheckUtil`、`AiriHttpClientImpl` 等）**jadx 没有解出**，所以「只看 jadx 目录」会得出错误结论（例如误以为没有 `TechSDKUnityPlayerActivity`）。

为拿到权威的类/字段/方法清单，我**没有重新反编译**，而是用 python 只读解析 dex 的 `string_ids / type_ids / field_ids / method_ids / class_defs` 表（脚本在 `/tmp/baj/`，输出写 `/tmp`）：

```bash
WS=/data/user/0/com.ai.assistance.operit/files/workspace/9dc0fd0c-7cad-4366-8d0b-bad7165d8587
python3 /tmp/baj/dexclass.py $WS/audit/ba-apk/classes.dex $WS/audit/ba-apk/classes2.dex > /tmp/baj/classes.txt   # 15912 个类名
python3 /tmp/baj/decl.py <dex> <类全名...>                    # 按类枚举 FIELD/METHOD + 签名
python3 /tmp/baj/main2.py <dex> strings /tmp/baj/strN.txt     # 导出字符串表（用于关键字检索）
```

覆盖度对照（`find ... -name '*.java' | wc -l` vs dex 类数）：com/tech 5 vs 41、com/unity3d 68 vs 156、com/airi 914 类中 jadx 仅部分、com/ace 4 vs 4。

**局限（必须写明）**：本次只做「声明级枚举 + 字符串表检索」，**没有解码指令流**，因此「谁调用了谁 / 某检测是否真的被执行」一律标注未验证；下文每条结论都带证据来源。

---

## 1. 包结构地图 —— 游戏主体不在 Java 层

| 包 | 类数 | 性质 | 证据 |
|---|---|---|---|
| `com.RoamingStar.BlueArchive` | **20** | 全部是 `BuildConfig` + `R$*`，**零业务代码** | `grep '^com\.RoamingStar' /tmp/baj/classes.txt` |
| `com.tech.*` | 41 | 发行壳：`TechApplication`、`TechSplashActivity`、`TechSDK`、`TechSDKUnityBridge`(+$1..$27)、`TechSDKUnityPlayerActivity`、`AbsSDKUnityBridge` | 同上 `grep '^com\.tech\.'` |
| `com.ace.gshell` | 4 | 腾讯 ACE 加固/反外挂壳：`AceApplication`、`GP6Service`、`GP7Service`、`GP7Worker` | 同上 |
| `com.unity3d.player` | 156 | Unity 运行时 Java 侧（`UnityPlayer`/`UnityPlayerActivity` + 混淆辅助类 `C0294d`/`H0` 等） | 同上 |
| `com.airi.*` | 914 | AirSDK/发行 SDK 主体（登录/支付/实名/网络/模拟器检测） | 同上 |
| `com.yostar.*` | **1** | 只有 `com.yostar.supersdk.UnityFileProvider`（SuperSDK 主体不在这两个 dex） | 同上 |
| 三方 SDK | — | taptap 1542、huawei 991、jiguang 817、alipay 374、adjust 268、tencent.mm 213、bytedance 154、**ishumei（数美）193**、**turingfd（腾讯防水墙/Turing）201**、miitmdid 90（OAID）、netspeed 66、shuzilm 49、okhttp3 321、retrofit2 115、gson 181 | `for p in ...; do grep -c "^$p" classes.txt` |

**结论**：Java 层是「生命周期 + 发行 SDK + 风控/反作弊 + 支付/推送」的壳。游戏逻辑在 native：
- `lib/arm64-v8a/libil2cpp.so` = **270,927,056 B**
- `assets/bin/Data/Managed/Metadata/global-metadata.dat`（`zip_listing.txt:14262`）
- `lib/arm64-v8a/libunity.so` = 20,950,552 B

（IL2CPP metadata 是否加密由 ba-il2cpp-survey 负责，本报告不重复结论。）

---

## 2. 入口与生命周期（类名 + 方法 + 文件:行号）

### 2.1 启动链
1. **Launcher**：`com.tech.core.TechSplashActivity`
   - `AndroidManifest.xml:224-252`：`exported="true"`、`screenOrientation="landscape"`、`hardwareAccelerated="true"`、`MAIN/LAUNCHER`。
   - `TechSplashActivity.java:15,33` `onCreate()` → `startGameActivity()`；`TechSplashActivity.java:36-39` `startActivity(new Intent(this, Class.forName(getForeActivity())))` 然后 `finish()`；`TechSplashActivity.java:49-51` `getForeActivity()` 读 `PackageManager.getActivityInfo(...).metaData.getString("next.activity")`。
   - Manifest 里该 meta 值 = `com.tech.sdk.bridge.TechSDKUnityPlayerActivity`（`AndroidManifest.xml:235-237`）。
2. **主 Activity**：`com.tech.sdk.bridge.TechSDKUnityPlayerActivity`
   - `AndroidManifest.xml:254-269`：`exported="true"`、`launchMode="singleTask"`、`screenOrientation="userLandscape"`、`hardwareAccelerated="false"`、`configChanges` 全量、`meta-data unityplayer.UnityActivity=true`。
   - 父类：`com.unity3d.player.UnityPlayerActivity`（`classes2.dex` class_def；`grep TechSDKUnityPlayerActivity /tmp/baj/cls2.txt`）。
   - **它只声明 4 个方法**：`<init>()V`、`onDestroy()V`、`onResume()V`、`onStop()V`（`python3 /tmp/baj/decl.py classes2.dex com.tech.sdk.bridge.TechSDKUnityPlayerActivity`）。
     → `onCreate` / `onPause` / `dispatchKeyEvent` **没有重写**，仍走父类实现。
3. **Application**：`com.tech.core.TechApplication`（`AndroidManifest.xml:185`）
   - 父类 `com.ace.gshell.AceApplication`（classes2 class_def）。
   - `AceApplication.java:31` `System.loadLibrary("tprt")`；`:16-28` 声明 `gp6ioctl/gp7ioctl/handleLoad(byte[],int,int)/handleLoadV22/ioctl/initialize` 六个 native 方法；`:41-68` `attachBaseContext()` → `attachBaseContextShell()` → `native initialize(pkg, filesDir, nativeLibDir, sourceDir, splits)`。
   - 即：**每个进程的 Application 一 attach 就初始化 ACE 壳**（`libtprt.so` 1,692,296 B）。

### 2.2 多进程 / 代理组件
`AndroidManifest.xml` 中 `android:process=`：`:GP7Worker`(:200)、`:GP6Service`(:209)、`:GP7Service`(:218)、`:pushservice`(:553)、`:pushcore`(:625/:692/:715)。
→ 插件必须**只在主进程**做 overlay；否则 5 个附加进程各挂一份会重复/互相干扰。

### 2.3 UnityPlayer 关键成员（ImGui 注入相关，均为 dex 权威枚举）
`com.unity3d.player.UnityPlayer extends android.widget.FrameLayout`：

- **字段**
  - `public static Activity currentActivity`（`class_data` access_flags=0x9 = public+static，唯一一处能直接拿到 Activity 的静态字段）
  - `mUnityPlayer : com.unity3d.player.UnityPlayer`（在 `UnityPlayerActivity` 里，`FIELD com.unity3d.player.UnityPlayerActivity.mUnityPlayer : Lcom/unity3d/player/UnityPlayer;`）
  - `mGlView : android.view.SurfaceView`、`m_PersistentUnitySurface : Lcom/unity3d/player/F`、`mActivity : android.app.Activity`、`mState`、`mQuitting`、`mProcessKillRequested` 等
- **方法**（截选，完整见 `/tmp/baj/up.txt`）
  - `UnitySendMessage(String,String,String)V`、`nativeUnitySendMessage(String,String,[B)V`
  - `getActivity()Landroid/app/Activity;`、`getView()Landroid/view/View;`
  - `CreateGlView()Landroid/view/SurfaceView;`
  - `pauseV()`、`resumeV()`、`onPauseV()`、`onResumeV()`、`pauseUnityV()`、`windowFocusChangedV(Z)`、`destroyV()`
- `com.unity3d.player.UnityPlayerActivity` 声明了 `onCreate(Bundle)`、`onPause()`、`onResume()`、`onDestroy()`、`dispatchKeyEvent(KeyEvent)`、`onWindowFocusChanged(Z)`、`onTouchEvent(MotionEvent)`、`updateUnityCommandLineArguments(String,String)`（`/tmp/baj/tech.txt`）。

**与现有 AzusaBA 的关系（直接可改的点）**：`AzusaBA/.../HookLoad.java:244` 把 Activity 类名写死为 `com.unity3d.player.UnityPlayerActivity`。本作真实 Activity 是它的**子类** `com.tech.sdk.bridge.TechSDKUnityPlayerActivity`——因为子类没重写 `onCreate`/`dispatchKeyEvent`，现有 hook **仍然生效**（父类方法会被继承调用），但 `onResume/onStop` 被子类重写，**hook 父类的 onResume 不一定触发**，应改为 hook 子类。

---

## 3. Java 层可 hook / 可篡改清单（按价值排序，主表 8 条）

> 可行性判定基准：类/方法**在 dex 中确实存在**（枚举证据）；「可行性」是对 Xposed/LSPosed 的技术可行性，不代表安全（风控另算）。

| # | 类#方法签名 | 用途 | 可行性 | 风险 |
|---|---|---|---|---|
| 1 | `com.unity3d.player.UnityPlayer#currentActivity`（public static 字段） | 不 hook 就能拿到当前 Activity（overlay 宿主、后续 addView） | **高**（纯读） | 低 |
| 2 | `com.tech.sdk.bridge.TechSDKUnityPlayerActivity#onResume()V` / `#onStop()V`（本类 override） | 精确前后台回调，用于 overlay 暂停/恢复、防截图/防掉线判断 | **高**（自有 override，不依赖父类） | 低 |
| 3 | `com.unity3d.player.UnityPlayerActivity#onCreate(Landroid/os/Bundle;)V`（after） | 注入时机（`setContentView(mUnityPlayer)` 之后）；主 Activity 未重写 → 会被继承调用 | **高** | 中（ACE 是否校验 Activity 链未验证） |
| 4 | `com.unity3d.player.UnityPlayer#CreateGlView()Landroid/view/SurfaceView;` | 拿到/包装 Unity 的 SurfaceView；overlay 需要知道它的尺寸与 z 序 | 中（返回类型必须仍是 SurfaceView） | 中（Unity 原生按自己创建的 view 假设尺寸/生命周期） |
| 5 | `com.unity3d.player.UnityPlayer#UnitySendMessage(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V` | **Java→C# 唯一官方单向通道**（C# 侧需有 GameObject 接收者） | 高（public static，native 实现） | 高（目标 GameObject/方法名不在 Java 层，猜错会抛/崩；C# 侧是否存在可调用接收者未验证） |
| 6 | `com.tech.sdk.TechSDK$SdkCallBack#onCallBack(Ljava/util/HashMap;)V` | 发行 SDK **所有异步回调的单点**（登录/支付/实名/切换账号结果都在这里） | 高 | 低（只观察）；改写返回值会改变游戏流程 |
| 7 | `com.tech.sdk.TechSDK#userEventUpload(Activity,String,HashMap)`、`#roleInfoUpload(Activity,GameRole)`（桥接层同名方法 `TechSDKUnityBridge#userEventUpload/roleInfoUpload`） | 埋点 / 角色信息上报，**可静态关闭统计** | 高 | 中（影响运营活动与画像；不等于能降风控，见 §6.7） |
| 8 | `com.ishumei.smantifraud.l111l11111I1l.l1111l111111Il#{l111l11111I1l(), l111l11111Il(), l111l1111l1Il(), l11l111l11Il()}` | **数美反作弊的 Java 侧 Xposed/EdXposed 检测**（详见 §3.1） | 中（public static、类名稳定） | **高**（结果直接进风控上报；改错值本身即异常特征） |

### 3.1 数美（com.ishumei）Xposed 检测细节（本报告最硬的安全性证据）
文件：`jadx/sources/com/ishumei/smantifraud/l111l11111I1l/l1111l111111Il.java`

- `:305-309` `l111l11111I1l()` → 文件存在性 `l1111l111111Il("XposedBridge.jar")`
- `:313-323` `l111l11111Il()` → `ClassLoader.getSystemClassLoader().loadClass("de.robv.android.xposed.XposedHelpers")`，再读 **`fieldCache` / `methodCache` / `constructorCache`** 三个静态缓存 → **能枚举出我们 hook 过的方法/字段**
- `:344-...` `l111l1111l1Il()` → `Class.forName("de.robv.android.xposed.XposedBridge")` 的 `getDeclaredFields()`
- `:382` `XposedBridge$CopyOnWriteSortedSet`
- `:471-483` `XposedInit.loadedModules`
- `:500` `Class.forName("com.elderdrivers.riru.edxp.config.EdXpConfigGlobal")` → **EdXposed 检测**
- `:675-694` `XposedInit.loadedPackagesInProcess` + `XposedHelpers`，且 `:693` 有诱饵串 `de.robvf.android.xposed.XposedHelpers`

其余检测类/串（静态命中，未定位到具体类，标注未验证）：
`/system/bin/su`、`/system/xbin/su`、`magisk`、`ro.kernel.qemu`、`ro.debuggable`、`goldfish`、`test-keys`、`TracerPid` 均在 dex 字符串表命中；**`xigncode`/`wellbia`/`GameGuard` 命中 0**；无 `frida`/`27042`/`gum-js-loop`/`linjector`/`substrate` 等 Frida 特征串（`frida` 的 4 次命中是超长正则里的假阳性）。

Java 侧自带 root 检测的唯一具名类：`com.mobile.auth.gatewayauth.utils.security.CheckRoot`（一键登录 SDK，jadx 未解出）。
发行 SDK 侧模拟器检测（类名/方法权威）：`com.airi.official.core.utils.emulatortools.EmulatorCheckUtil`（`checkFeaturesByAbi/Board/BaseBand/Cgroup/Flavor/Hardware/Manufacturer/Model/Platform`、`getInstalledSimulatorPackages`、`getSensorNumber`、`getProperty`、字段 `PKG_NAMES`）+ `CommandUtil.exec(String)`（真正 `Runtime.exec("sh")` 跑命令，`CommandUtil.java:42-...`）+ `CheckResult`（`RESULT_EMULATOR/RESULT_MAYBE_EMULATOR`）。

### 3.2 网络层与请求签名
- SDK 网络：`com.airi.core.data.net.http.AiriHttpClient` / `AiriHttpClientImpl`、`com.airi.core.data.net.NetworkModule`、`SDKServiceApi`（类名来自 dex）；底层 okhttp3(321)+retrofit2(115)；TapTap 还自带一份 `com.taptap.sdk.okhttp3`。
- **请求签名/AES**：`jadx/sources/com/airi/core/sign/AiriSgClient.java:5-13`
  ```java
  public static native String getAAesIv();
  public static native String getAAesKey();
  public static native String sign(byte[] bArr, int i);
  static { System.loadLibrary("airisgcore"); }
  ```
  → **Java 层可直接拿到 AES Key/IV 与签名结果**（native 实现，`libairisgcore.so` 2,658,312 B）。这是 Java 侧唯一高价值的「能看明文」的密码学接口。
- 游戏业务 base url：**dex 字符串表里没有**（`grep -ahoE 'https?://[A-Za-z0-9._-]+'` 只得到 SDK 域名：openmobile.qq.com、mclient.alipay.com、tapsdk.*、adjust、cmpassport 等），推断在 `assets/SDKConfigSettings.json` 或 native（未验证）。
- 证书固定：dex 中 **没有 `sha256/...` pin 字面量**（`grep -acE 'sha256/[A-Za-z0-9+/=]{20,}'` = 0/0）；存在 `com.taptap.sdk.okhttp3.CertificatePinner`，是否启用未验证。

### 3.3 native 库 → Java 调用点（`grep -rn 'loadLibrary("' jadx/sources`）
| so | Java 加载点 | 备注 |
|---|---|---|
| libtprt.so | `com/ace/gshell/AceApplication.java:31` | ACE 壳，Application attachBaseContext 即加载 |
| libairisgcore.so | `com/airi/core/sign/AiriSgClient.java:12` | 签名 + AES key/iv |
| libsigner.so | `com/adjust/sdk/sig/NativeLibHelper.java:10` | Adjust 签名 |
| libthemis.so | `com/taptap/sdk/themis/lite/ThemisLite.java:58` | TapTap 安全 SDK（`InitThemis_v2`/`Register`/`Z8f7JxQkV`） |
| libdu.so | `cn/shuzilm/core/k.java:12` | 数盟设备指纹 |
| libjutils.so | `cn/jiguang/internal/JNAction.java:13` | 极光 |
| libmsaoaidauth.so | `com/bun/miitmdid/core/CertChecker.java:11` | OAID |
| libn.so | `com/bytedance/ad/common/interal/Nano.java:6` | 穿山甲 |
| libmsaoaidsec.so / libsmsdk.so / libtapsdkcore.so / libturingad.so | 字符串命中（1/2、6、1、1 次）但加载类未被 jadx 解出 | 数美/移动安全联盟/TapTap/腾讯 Turing，**具体调用点未验证** |

反作弊/风控三件套（静态存在，**是否实际初始化未验证**）：
`com.ishumei.smantifraud.SmAntiFraud#create(Context,SmOption)` + `getDeviceId()`；`com.tencent.turingfd.sdk.ams.ad.TuringSDK#createConf/init()`、`TuringRiskService`、`TuringIDService`；ACE（`AceApplication.initialize` + `:GP6Service/:GP7Service/:GP7Worker` 三个 exported 独立进程服务）。

---

## 4. Java 层是否存在战斗数值 / 掉落 / 奖励逻辑？—— **不存在**

证据（三条独立证据链）：
1. **类名层面**：`grep -icE '\.(Battle|Stage|Mission|Gacha|Raid|Enemy|Unit|Skill|Reward|Drop|Loot)' /tmp/baj/classes.txt` 命中 243 条，但剔除三方 SDK/androidx 后 **为 0**；`com.RoamingStar.*` 仅 20 个类且全是 `BuildConfig`/`R$*`。
2. **字符串层面**：`damage / critical / gacha / drop_rate / reward` 在 classes.dex 字符串表命中 **0 / 0 / 0 / 0 / 0**（classes2 同样 0）。
3. **结构层面**：`libil2cpp.so` 270,927,056 B + `global-metadata.dat` 存在 + `assets/bin/Data/Managed/` 下 C# 程序集资源 → 标准 IL2CPP 构建；dex 中没有任何 `UnityEngine.*` / `Il2Cpp.*` 绑定类。

→ **改数值/掉落/抽卡/奖励在 Java 层没有任何可篡改的入口**，必须走 IL2CPP/native（见 §6）。

---

## 5. Manifest 关键项（`jadx/resources/AndroidManifest.xml`）

| 项 | 值 | 行 |
|---|---|---|
| minSdk / targetSdk | **24 / 33** | `:11-13` |
| `android:debuggable` | **未出现** → 默认 false（release 不可调试） | grep 无命中 |
| `usesCleartextTraffic` | **true** | `:188` |
| `networkSecurityConfig` | `@xml/http` | `:189`（jadx 未导出 `res/xml`，**具体域名白名单未验证**） |
| `allowBackup` | false | `:186` |
| `extractNativeLibs` | true | `:187` |
| `requestLegacyExternalStorage` | true | `:192` |
| `appComponentFactory` | `androidx.core.app.CoreComponentFactory` | `:191` |
| Application | `com.tech.core.TechApplication` | `:185` |
| meta-data | `AnoStamp=SKuFlKioqKmoqKipZwiM3mcIjN8=`（`:194-196`）、`unityplayer.UnityActivity`、`unity.splash-mode/enable`、`unity.launch-fullscreen`、`unity.auto-report-fully-drawn`、`JPUSH_APPKEY/JCORE_*`、HMS min_api_level、`com.taptap.services.update.loader`、`android.max_aspect=2.4` | — |
| uses-library | `org.apache.http.legacy` | — |
| ABI | **仅 arm64-v8a** | `ls lib/` |

**导出组件 24 个**（脚本 `/tmp/baj/manifest_exp.py` 解析），关键：
- `service com.ace.gshell.GP7Worker`(:197) / `GP6Service`(:206) / `GP7Service`(:215)：`exported=true` + 独立进程 + 自定义 action（反作弊 IPC 面）
- `activity com.tech.core.TechSplashActivity`(:224)、`com.tech.sdk.bridge.TechSDKUnityPlayerActivity`(:254)
- 支付/登录回调：`com.alipay.sdk.app.PayResultActivity`(:310)、`AlipayResultActivity`(:316)、`com.taptap.sdk.login.ui.TapTapLoginActivity`(:349)、微信 `WXEntryActivity`(:418/:425)、`WXPayEntryActivity`(:472/:477)、`com.tencent.tauth.AuthActivity`(:432)、微博 `ShareTransActivity`(:509)
- 推送：HMS `PushMsgReceiver`(:529)/`PushReceiver`(:539)/`HmsMsgService`(:549)/`PushProvider`(:560)、JPush `PopWinActivity`(:667)/`PushActivity`(:677)/`JNotifyActivity`(:717)/`JTransitActivity`(:728)

---

## 6. §五 素材：不可行 / 低收益的 Java 方向（含理由与证据）

1. **改战斗数值、掉落、抽卡、奖励** → Java 层无对应类与字符串（§4 三条证据），也无可用的数据通道。
2. **用 Java 反射/JNI 直接改 Unity 对象（Il2Cpp 对象、Character/Unit）** → dex 无任何 IL2CPP/UnityEngine 绑定类，Unity 对象不在 JVM 堆里；只能 native inline hook（libil2cpp.so 270MB）。Java 唯一出口是 `UnitySendMessage` 单向下发，且要求 C# 侧预先挂了接收 GameObject。
3. **把 ImGui 画进 Unity 的 GL 上下文（共享纹理 / 劫持 glDraw / swap interval）** → Unity 自己创建 EGLContext/EGLSurface，Java 层拿不到句柄（`UnityPlayer.CreateGlView()` 只给 `SurfaceView`，不给 EGL 对象）。可行做法只有「独立 EGL + 独立 SurfaceView 叠加层」（即现有 `GLES3JNIView` 模式），**无法与 Unity 共享纹理或读取其帧缓冲**。
4. **拦截/改写游戏网络协议（战斗结算、掉落请求）** → Java 的 okhttp/retrofit 只服务发行 SDK（`AiriHttpClientImpl`、TapTap 自带 okhttp3）；游戏流量在 libil2cpp/libunity。Java 侧改不了结算请求，也看不到战斗封包。
5. **用 Java 层“关掉反作弊”** → ACE 的注入与检测都在 native：`AceApplication.initialize(...)`（native，`AceApplication.java:28`）+ `loadLibrary("tprt")`（`:31`）+ `:GP6/:GP7` 三个独立进程服务 + `gp6ioctl/gp7ioctl/ioctl`。Java hook 只能让 `initialize` 失败（非 0 直接抛异常，`:62-63`），不会停掉已起的 native 线程/扫描；收益低、崩溃/风控风险极高。
6. **证书固定绕过** → dex 无 `sha256/` pin 字面量（0 命中）；即便 hook `TrustManager`/`X509TrustManager`，也只影响 SDK 的 Java 请求，对 native/Unity 流量无意义。
7. **靠关埋点降低被检测概率** → 反向风险：`userEventUpload/roleInfoUpload` 走的是发行 SDK 运营通道，数美/Turing 是独立风控通道；关掉只丢统计，不减风控特征，反而可能因“角色信息缺失”引起服务端校验差异（推断，未实测）。
8. **替换 Application / Activity 类（换壳、二次代理）** → `TechApplication extends AceApplication`，Application 的 `attachBaseContext` 是 ACE 初始化入口；替换/绕过会改变 native 初始化时序（推断：直接风控/崩溃，未实测）。正确做法是 LSPosed 在 `handleLoadPackage` 阶段挂 hook，而不是换类。

---

## 7. 给 report §二 / §五 的写法建议（可直接粘）

### §二（注入入口/可行性）建议结构
- **2.1 入口链（3 行）**：`com.tech.core.TechSplashActivity`（MAIN/LAUNCHER，`Manifest:224`）→ 读 meta `next.activity` → `com.tech.sdk.bridge.TechSDKUnityPlayerActivity`（`Manifest:254`，`singleTask`、`exported`、`unityplayer.UnityActivity=true`，父类 `com.unity3d.player.UnityPlayerActivity`）→ UnityPlayer 实例挂在该 Activity 的 `mUnityPlayer` 字段。
- **2.2 Application 与反作弊初始化**：`com.tech.core.TechApplication extends com.ace.gshell.AceApplication`；`attachBaseContext → attachBaseContextShell → native initialize(...) + loadLibrary("tprt")`。结论：注入必须走 LSPosed 正常 `handleLoadPackage`，「替换 Application/二次代理」不可行。
- **2.3 注入入口（按稳定性排序）**：
  ① hook `TechSDKUnityPlayerActivity.onResume()/onStop()`（本类 override，最稳）；
  ② hook `UnityPlayerActivity.onCreate(Bundle)` after（子类未重写 → 会被继承调用）；
  ③ 直接读 `UnityPlayer.currentActivity` 取 Activity；
  ④ 在 Activity 的 decor 上 `addView` 一个独立 `GLSurfaceView` 叠加层（现有 GLES3JNIView 模式）；
  ⑤ 需要 Unity 的 SurfaceView 引用时 hook `UnityPlayer.CreateGlView()` 在返回时保存。
- **2.4 进程注意**：只在主进程注入；`:GP6Service/:GP7Service/:GP7Worker/:pushservice/:pushcore` 不装 overlay（`Manifest:200/209/218/553/625`）。
- **2.5 与现有 AzusaBA 代码的差异（必须写进报告）**：
  - `HookLoad.java:244` 写死 `com.unity3d.player.UnityPlayerActivity`；本作真实 Activity 是子类 `TechSDKUnityPlayerActivity`，`onCreate/dispatchKeyEvent` 未重写 → 现有 hook 仍生效，但**建议改为 hook 子类 + 父类兜底**。
  - `docs/ANTICHEAT.md` 里“XIGNCODE3”与本包不符：dex 中 `xigncode/wellbia/GameGuard` **0 命中**；实际是 **ACE(gshell+libtprt) + 腾讯 Turing + 数美 Shumei + TapTap Themis**。
  - 数美会在 Java 层枚举 `XposedHelpers.fieldCache/methodCache/constructorCache` 与 `XposedBridge` 字段、`XposedInit.loadedModules/loadedPackagesInProcess`、`EdXpConfigGlobal`（§3.1）→ 这是对 LSPosed 插件的**真实静态检测面**，必须在测试机上实测其是否被初始化与上报。

### §五（不可行方向）建议写法
按 §6 的 8 条，每条统一格式「方向 → 为什么在 Java 层做不到 → 证据」；核心三条（数值/Unity GL/游戏协议）证据最硬，建议放在最前面。

---

## 8. 未验证清单（交给上游决策，不要在报告里当结论）

1. 数美 / Turing / TapTap Themis / AirSDK 是否**实际初始化**（初始化调用点在未解出的类里）。
2. `/system/bin/su`、`magisk`、`ro.kernel.qemu`、`test-keys`、`TracerPid` 等字面量归属哪个类（jadx 未解出；最可能是 `com.airi...emulatortools` 或数美）。
3. `res/xml/http.xml` 内容（jadx 未导出 `res/xml`；networkSecurityConfig 的明文/固定域名白名单未知）。
4. `assets/BA.acf` 的用途与内容（禁止解压，未读；`AceApplication` 有 `handleLoad(byte[],int,int)/IS_SELF_LOAD_DEX` 能力，但 `IS_SELF_LOAD_DEX=false`）。
5. `UnityPlayer.UnitySendMessage` 的 access_flags（未逐位核对；按 Unity 标准 API 应为 public static）。
6. `TechSDKUnityPlayerActivity.onResume/onStop` 内部调用了什么（未解码指令流）。
7. 游戏流量是否走 `UnityWebRequest`/native 自研（dex 无该字符串，推断 native）。
8. `libmsaoaidsec/libsmsdk/libtapsdkcore/libturingad` 的 Java 加载类（字符串命中但类未解出）。

---

## 9. 数美检测面的可执行规避建议（对应 §3.1）

结论先行：7 个检测点里只有 **三个 cache** 与 **EdXpConfigGlobal** 能在 LSPosed 侧真正「做空」；`XposedBridge` 类存在性、`getDeclaredFields`、`loadedModules`、`loadedPackagesInProcess` 属框架层无解，只能改检测方或接受指纹。

| 检测点 | LSPosed 侧能做 | 做不到 / 代价 |
|---|---|---|
| `XposedHelpers.fieldCache/methodCache/constructorCache`（:313-323） | ① 全模块不用 `XposedHelpers.find*`，改用 `Class.getDeclaredMethod` + `XposedBridge.hookMethod`（此路径不写 cache）；② 每次 hook 后反射 `clear()` 三个 HashMap（仅 lookup 加速器，清空不影响已生效 hook）；③ hook 探测函数返回空 Map | 三个 `static final` 字段删不掉，`Class.forName` 必成功；若判据是「类存在」而非「size>0」则 clear 无效（判据未验证，§8-1）；cache 进程级共享，别的模块用了会重新填 |
| `XposedBridge.getDeclaredFields()`（:344-…） | 少留痕：不打 `XposedBridge.log`、不用 `hookAllMethods`、hook 前不调 `XposedHelpers` | `sHookedMethodCallbacks/sHookedConstructorCallbacks/disableHooks` 无法删除改名；`XposedBridge` 被 LSPosed 注入即加载，此项必然命中；LSPosed 无「对目标隐藏 Xposed」官方特性 |
| `XposedInit.loadedModules`（:471-483） | 只能缩小作用域：仅勾游戏主进程，不勾 `:GP6/:GP7/:GP7Worker/:pushservice/:pushcore` | 最致命一条：含模块包名/APK 路径/ClassLoader，被读＝自报模块；无反注册 API（反注册即 hook 失效），静态集合无法置空 |
| `XposedInit.loadedPackagesInProcess`（:675-694） | 同上，最小作用域；不无故 `Class.forName` | 无框架手段；:693 有诱饵串 `de.robvf...`，说明该分支带字符串比对，写死包名的规避可能被绕过 |
| `EdXpConfigGlobal`（:500） | **无需处理**：EdXposed 专有类，LSPosed 下 `Class.forName` 抛 CNFE，天然阴性 | 只需确保不引入 EdXposed 兼容层 |
| `XposedBridge$CopyOnWriteSortedSet`（:382） | 待确认 LSPosed 是否保留该内部类；不保留则天然阴性 | 若保留则与 `getDeclaredFields` 同性质，无解 |
| `XposedBridge.jar` 文件存在性（:305-309） | 无关：LSPosed 不落该 jar，天然阴性 | — |

三条硬边界：
1. 最有效的规避不是「藏」而是 hook 三个探测方法改返回值（`l111l11111I1l/l111l11111Il/l111l1111l1Il`），但那是「改检测方」，且新增 ART 方法篡改特征（deopt/inline），只能作测试机实验分支，不进默认构建。
2. 数美在 native 侧还可读 `/proc/self/maps` 找 `liblspd.so`/riru 痕迹、读 `TracerPid`，完全在 Java 层之外，LSPosed 无手段；「Java 层零痕迹」≠「不被检测」。
3. 报告口径应为：§3.1 是「LSPosed 插件必然留下可枚举静态指纹」的证据，不是「可以被清理干净」的清单；可执行动作只有「不用 XposedHelpers + 最小作用域 + 清 cache」三件，其余必须测试机实测（§8-1）。

### 9.1 `HookLoad.java` 修改建议（一句可直接执行）
把当前 `HookLoad.java:234` 的 `activityClassName` 从 `"com.unity3d.player.UnityPlayerActivity"` 改为 `"com.tech.sdk.bridge.TechSDKUnityPlayerActivity"`，并仅用它 hook 本类 override 的 `onResume()V` 与 `onStop()V`（`findAndHookMethod(cls, "onResume", hook)` 无参重载），而 `onCreate(Landroid/os/Bundle;)V` 与 `dispatchKeyEvent(Landroid/view/KeyEvent;)Z` 继续留在 `com.unity3d.player.UnityPlayerActivity` / `android.app.Activity` 上（子类未重写，继承调用即可命中原 hook）——即「子类管前后台、父类管注入与按键」。
