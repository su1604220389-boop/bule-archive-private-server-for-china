# 23 — 主线改判：TLS 已通，卡点在应用层

> 时间：2026-11-14 01:55 前后
> 依据：`srv-ops` 的 pcap 逐流视图 + nginx 日志 + 我们实际回出去的 180 B 原文

---

## 一、改判的触发证据

### 1. `state-api.bluearchive-cn.com` 这条连接，TLS 全程走完了

| 阶段 | 实测 |
|---|---|
| ClientHello | 353 B，**带 SNI `state-api.bluearchive-cn.com`** |
| ServerFlight | ≈2917 B / 2894 B（属「我们自己的链」区间，远大于 `CN=default` 的 1355 B） |
| 之后 | ClientKeyExchange(37) → CCS(1) → Finished(32) → **应用数据 APP(339)** |
| 协议 | **TLS 1.2**（非 1.3，故后续记录结构可读） |
| nginx | `GET /api/state` → **200 / 180 B**，reqlen=323 |
| 次数 | 两次：01:34:52、01:37:00 |

⇒ **ServerFlight 之后出现应用数据且 nginx 解出明文请求并回 200 = TLS 通过。**

### 2. `gsqc-api` 也不卡在 TLS
01:25:00 那条：CH 440 B、带 SNI、ALPN 仅 http/1.1、sigalgs 无异常 → flight ≈2600 → CCS(1) → APP(53)(112)(19)。**握手成功**，之后客户端自己停了。
（另：`gsqc` 的 nginx access 无记录，说明该连接可能没被 DNAT 劫持、直接打到了真实后端，或落在未监听的 vhost。）

### 3. 决定性负面证据
**`/api/state` 200 之后，客户端什么网络请求都没发。**
- `gsqc-api`：零条 ClientHello
- `static.bluearchive-cn.com`：零条
- `example.com/api/`：零条（该 log 里 `UnityPlayer` 计数 = 0，全是 okhttp 的 SDK 调用）

---

## 二、改判结论

> **卡点不在证书链、不在 TLS、不在网络层。卡在「客户端收到我们自己编的 `/api/state` 应答之后，到下一跳之前」——客户端在本地就停了。**

### 被撤下主线的东西
- 系统 CA 注入（PEM/DER、label、APEX、mount namespace 传播）
- 证书链、pinning 假设
- `nsenter --rbind` 注入（指令已撤回，不冒险）
- Frida / 运行时 hook

### 被推翻的旧结论
| 旧结论 | 实际 |
|---|---|
| 客户端**不发 SNI** | `state-api` 这条**明确带 SNI**。之前那条无 SNI 的观察来自别的连接（很可能是 gsqc 或裸 IP 连接） |
| 客户端拒绝 = 证书不受信 | `state-api` 在 CA 未正确落库时就已经 TLS 通过了 → 该路径根本不校验或放宽了校验 |

---

## 三、新的主线假设

我们回的 180 B：
```json
{"Servers":["https://example.com/api/"],"State":0,"Msg":"","CallbackUrl":"","CustomerServiceUrl":"","AddressablesCatalogUrlRoots":["https://static.bluearchive-cn.com/prodm39"]}
```

**这份 schema 从未与真实上游核对过**：字段集合、字段名大小写、嵌套结构、`State` 取值语义、是否缺必填字段——全都未知。

客户端反序列化后判定「不能继续」，于是在本地停住（最可能是弹了错误框或停在加载态等用户操作）。

---

## 四、当前派单

| 谁 | 任务 | 状态 |
|---|---|---|
| `phone-ops` | 截图逐字描述 + 进程 wchan/线程 + logcat 五组错误 grep + 崩溃栈。**CA 相关工作全部停止** | 已下达 |
| `srv-ops` | ①`example.com/api/` 入口是否存在、返回什么 ②`/api/state` 的 `return 200` 位置、备份、reload 与回滚流程 ③打开「下一跳」日志可观测性 ④抓包切到无 IP 过滤的 `r_013747` | 已下达 |
| 上游取证子代理 | 从真实上游拿 `state-api` / `gsqc-api` / `example.com` / `static` 的真实应答、证书、DNS、SNI 依赖性 | 运行中 |
| frida 调研 | 已完成，结论降级为备选（见 §五） | ✅ |

---

## 五、frida 调研的可用结论（降级保留，不再作为主线）

1. **Android 17 对 `targetSdk≥37` 的 app 强制 Certificate Transparency（必须有 SCT）**。我们是 `targetSdk=33`，**暂时豁免**——但这是定时炸弹，客户端一旦升到 37，"装 CA"这条彻底死。
2. Android 14+ 系统 CA **按进程单独挂载**（HTTP Toolkit 原文："individually mounted directly into each process"）→ 这就解释了「文件在、格式对、label 对，进程却看不见」。**判定实验：`nsenter --mount=/proc/<pid>/ns/mnt -- ls /apex/com.android.conscrypt/cacerts | wc -l`，146 = 不可见，147 = 可见。**（已暂缓，但留作将来若真需要时的一发子弹）
3. `TrustManagerFactory` / `AndroidCAStore` **进程内有缓存**，改磁盘后必须冷启动。
4. Frida 17.25.2 最新；**KSU + Android 15/16 上 spawn 模式会 timed out，严重时 zygote64 SIGABRT 导致手机重启**（frida/frida#2516）；attach 模式正常但赶不上早期 `SSLContext.init`。
5. `frida-il2cpp-bridge` 在本项目**直接不可用**：它走 `getExportByName("libil2cpp.so","il2cpp_*")`，而我们的 `.dynsym` `st_name` 已被清零。
6. 若将来真的需要绕 TLS，优先级：**改 `res/xml` 的 networkSecurityConfig（本项目已实测 `res/*` + `resources.arsc` 改动不会被 ACE 杀）> 协议降级到 `http://`（metadata 里默认 ApiUrl 就是 `http://test-ba.yostar.net:5210/api/state`，消费端接受明文）> 从 `libil2cpp` 的 `DT_INIT` 运行期内存补丁 `libunity`**。

---

## 六、不变的红线

1. 判 TLS 通过**只认 pcap**：ServerFlight 之后是否出现应用数据 / `GET` / `POST` / `PRI *`。
2. `access_log` 有记录 ≠ TLS 通过；`error_log` 为空 ≠ TLS 通过。
3. tcpdump 过滤**不能用 `not src net 172.24.0.0/16`**（服务器自己就在这个网段，会把整个 ServerFlight 滤掉）。用无方向过滤或按客户端 IP 钉死。**这是 Lead 今晚写错的口径，已纠正。**
4. 不给 `.so` 用 `cat > dst`。
5. `UseCustomExcel=true` 不得开启。
