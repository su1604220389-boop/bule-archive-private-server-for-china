# 网关地址来源：实测排除法（2026-11-13）

> 只记录**已实测**的结论；推断一律标注「推断」。

## 一、已确认可用（实测通过）

| 项 | 证据 |
|---|---|
| `assets/SDKConfigSettings.json` 改 `sdk_url` → SDK 登录全走我们 | 抓到 `/common/config`、`/user/login`、`/user/detail`、`/health-game/duration` 等请求 |
| 卡密校验（服务端） | `POST /user/login` 的 `OpenID` 就是卡密；输 `11111111111` 返回 200 + token |
| 登录页文案改造 | `res/layout/fragment_default_mobile_code_login.xml` + `res/values/strings.xml`，实测显示「卡密不正确」 |
| 改 `resources.arsc` / `res/*` 安全 | E32/E34/E36 均可启动 |
| 删除 `assets/__tpinfo.*` 安全 | 同上 |
| `libunity.so @0xA53A38` 4 字节补丁安全 | 同上（与官方行为一致，未见异常） |
| SDK 登录成功后的现象 | 枪毙在游戏自己的网关：原生弹窗「认证服务器拒绝了请求，将返回标题画面」 |

## 二、已实测排除（别再试）

| 假设 | 实测方法 | 结果 |
|---|---|---|
| **改客户端 `Hosts` 文件能换网关** | 把 `files/Hosts` 写成单条 `127.0.0.1:9443`（含真实时间戳、selected=1），启动游戏 | ❌ 9443 端口 **0 个连接**；游戏启动后把官方条目又写回去了 |
| **改 `LocalizeConfig.txt` 的 `ResUrls` 能劫持 CDN** | 指向 `https://127.0.0.1:9444/prodm39`，起 TLS 反向代理 | ❌ `cdn.log` **一条请求都没有**；游戏提示「网络异常，请重新连接」 |
| **网关域名编译进 APK 静态产物** | 全量扫 dex / libil2cpp / global-metadata / assets（ASCII + UTF-16） | ❌ 0 命中 |
| **网关域名在客户端 6227 个 TableBundles 里** | 解压全部表包扫 `bluearchive-cn` / `gsqc-api` / `state-api` / `ConnectionGroup` | ❌ 仅 1 处命中：`webseasonexceltable.bytes`（活动页 Web 链接，非 API） |
| **能改任意 `.so`** | 用自编译 so 替换 `libairisgcore.so`（NEEDED 干净、无人依赖） | ❌ **SIGBUS**（`ApplicationExitInfo: reason=2 SIGNALED status=7`），与文档「libtprt 改任意字节 → kill(SIGBUS)」一致 |
| **能用 Xposed Java hook** | `XposedBridge.hookMethod/hookAllMethods` | ❌ 进程内存在**混淆替身类** `LUnEw/z/NP/i/NLAT/v/Q/S/XposedBridge`，方法全部 `NoSuchMethodError` |
| **native GOT hook 可用** | 旧模块 `libdhook.so` | ✅ 可用（`installed=1 slots=3`），这是目前唯一可靠的注入手段 |

## 三、文档原有结论对本轮的约束（必须遵守）

1. `api-probe.md:34`：业务主机**不以字符串形式编译进 dex / so / metadata**；唯一来源是「运行期 `Hosts` 落盘 + 服务端下发」。
   → 但本轮实测证明：**`Hosts` 只被读写，不决定连接目标**。所以「服务端下发」这一半仍未被证实。
2. `ba-airisdk.md:185`：改 so → SIGBUS。已再次实测确认。
3. `ba-airisdk.md:244`：`原包名 + 删 tpinfo + 假 ACE/SG` 才是改包方向；**假 ACE 会破坏 Unity 需要的返回**，用户已明确否决。

## 三点五、本轮新增实测（补充）

| 实验 | 方法 | 结果 |
|---|---|---|
| `Hosts` 在**已登录**状态下是否被用于连接 | 写成单条 `127.0.0.1:9443`（8 字节字段设成比官方值大 1），设备已绑定卡密、启动即 quick-login | ❌ 9443 仍 0 连接；游戏反而把官方 `gsqc-api` 条目追加回去 → **`Hosts` 只是记录/展示，不决定连接目标** |
| SDK 是否有「下发服务器地址」的接口 | 全量翻阅 `sdk.log` 本次会话的全部请求 | ❌ 只有 `/common/config`、`/user/quick-login`、`/user/detail`、`/health-game/duration`、`/common/geo-ip`、`/heartbeat/pulse` 六个，**没有服务器列表类接口** |
| 官方响应里是否带 `gsqc` 主机 | 在 `sdk_resp/*.json` 搜 `gsqc` / `bluearchive-cn` | ❌ `gsqc` 0 命中；`bluearchive-cn` 只出现在 `static*` CDN 与适龄提示文本里 |
| 主机名是否在客户端文件里 | 扫 `categories/catalog_Remote.json`(81MB)、`HTTPCache/`(空)、`Cookies/`(空)、`ClientSaveData/`(空) | ❌ 全 0 |
| 主机名是否周期性异或混淆在 libil2cpp | 已知明文 `state-api.bluearchive-cn.com`，对 270MB 全文件做周期 L=1/2/3/4/6/8/12/16/24 的向量化筛选 | ❌ 全部 0 命中（不是简单异或；推断为 AES/拼接） |
| 「网络异常，请重新连接」的来源 | 停掉本机 `sdkcard.py` 后再启动游戏 | ✅ 该提示由 **SDK 连不上 `sdk_url`** 引起，与网关无关；服务端拉起后恢复为「认证服务器拒绝了请求」 |

**工作区纪律**：以上结论均为实测；未实测的推断已单独标注。

## 五、2026-11-13 收尾：两条决定性发现

### 5.1 `libunity` 的 4 字节补丁 = ACE 的触发点（实测对照）

| 版本 | libunity | 结果 |
|---|---|---|
| E32/E34/E36 | 打了 `@0xA53A38` 证书补丁 | 启动后 **SIGBUS（status=7，无 tombstone）** |
| **E42** | **原厂 libunity**（取 `audit/ba-apk/lib/arm64-v8a/libunity.so`） | ✅ **正常运行**，SDK 卡密登录通过，停在「认证服务器拒绝了请求」 |

结论：**ACE 会校验 `libunity.so`，命中即 `kill(SIGBUS)`**；`libil2cpp.so` 无 hash pin（`ace-ipc.md` §3）。
工程后果：**证书绕过（改 libunity）必须放弃**，后续一律走明文 HTTP。

### 5.2 网关地址的真实形态：`gameUrl`，由游戏传给 SDK

运行时内存（dalvik-main）里抓到 SDK 自己的日志原文：

```
[AiriSDK][1.16.1][13541][main][AiriSdkManager.kt:32 init]
activity=TechSDKUnityPlayerActivity, pid=CN-BA,
gameUrl=https://state-api.bluearchive-cn.com/api/state
```

- `gameUrl` 是 **`AiriSdkManager.init(...)` 的入参**，即「游戏告诉 SDK 该连哪」，不是 SDK 自己拼的
- 完整字符串 46 字节：`https://state-api.bluearchive-cn.com/api/state`
- `gameUrl` 在 `classes.dex` 里只作为**埋点字段名**和日志格式串出现，**值不在 dex**
- 该值在 APK 全量扫描中 0 命中（ASCII / UTF-16 均试过，含 manifest 的 UTF-16 字符串表）
- `libil2cpp` 与 `global-metadata.dat` 用该明文做**周期异或**反推（L=1..43），**全部 0 命中** → 不是简单混淆

### 5.2b 各改动面的实测容错矩阵（2026-11-13 补全）

| 改动对象 | 结果 | 版本 |
|---|---|---|
| `libunity.so`（4B 证书补丁） | ❌ SIGBUS | E36 |
| `libairisgcore.so`（整库替换） | ❌ SIGBUS | E35 |
| `classes.dex`（整包重编） | ❌ 卡 Android 启动界面 | E43 |
| **`classes2.dex`（只改一个 const-string）** | ✅ **正常启动、SDK 登录成功** | **E44** |
| `resources.arsc` / `res/*` / `assets/*` | ✅ 正常 | E32/E34/E42 |
| **`libil2cpp.so`（填充字节翻转）** | ✅ **正常启动（45s+ 存活）** | **E38** |

补充事实：**ACE 会持久化“判定结果”** —— 触发过一次（E43）之后，同一批 APK 会被连坐 SIGBUS，直到删除
`files/{ace_shell_di.dat, shell_cache, ano_tmp, data/app}` 才恢复。这解释了此前“同一版有时能跑有时被杀”的全部现象。

### 5.2c `gameUrl` 在登录流程里没有被使用

E44（把 `TechSDKUnityBridge$1.val$gameServerUrl` 强制成 `http://127.0.0.1:8080/api/state`）实测：
SDK 登录链照常走完（`/common/config` → `/user/quick-login` → `/user/detail` → …），
但 **`/api/state` 命中数 = 0** —— 说明 `gameUrl` 不参与登录，网关地址另有来源。

### 5.3 因此无 root 的可行切入点

既然值由「游戏（native）→ SDK（Java）」传递，而 **Java 侧代码在 dex 里、dex 未被 ACE 纳入 hash pin**，最直接的改法是把
`AiriSdkManager.init` 收到的 `gameUrl` 在 Java 层**替换成我们的地址**（smali 级 patch）。
先决条件：dex 改动不会被 ACE 处理 —— 需按 §5.1 同样方式做一次对照实验（改一个无害字符串常量 → 看是否 SIGBUS）。

## 四、当前唯一未解的问题（一句话）

**「客户端第一次连接网关前，那个主机名是从哪来的」**——静态三边 + 表包 + 两个落盘配置全部排除，只剩「运行时解密」这一种可能。

下一步验证方式（未做）：
- 在内存里定位该字符串所在的 **il2cpp string 对象**（而非裸字节），看它的持有者（`NetworkTask` 对象）能否反查到读取来源；
- 或用 native hook 拦截 `send/write`，直接拿到 `CONNECT ...:443` 的原始字节，确认客户端在**哪一步**拼出它。
