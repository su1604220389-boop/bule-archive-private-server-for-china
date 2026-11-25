# 25 — 根因定案：状态接口 schema 错误（非 TLS、非 CA、非 pinning）

> 时间：2026-11-14 01:50 前后
> 结论等级：**已证死**（有可复现实验 + 真实上游对照 + 逐像素取证）

---

## 一、根因（一句话）

> 我们伪造的 `/api/state` 应答**缺少真实 schema 的 5 个版本字段、并多了一个真实结构里不存在的 `Servers`**，客户端解析后读不到版本信息，判定状态异常，弹出「提示」框，并把我们回的空串 `Msg` 当作正文显示 —— **于是弹窗正文是空白的**。

---

## 二、证死路径（三步，全部可复现）

### 第 1 步：弹窗正文 = `Msg` 字段（探针实验）

把 `/api/state` 的 `Msg` 从 `""` 换成唯一标记 `PROBE-M1-STATE-ZQ7`，其余一字不动，两个 conf 同步改。

四帧截图（01:46:10 / 20 / 31 / 47）逐像素比对：

| 检测项 | p1 | p2 | p3 | p4 |
|---|---|---|---|---|
| 白色卡片 bbox | 1099×873 @ x[848..1946] y[195..1067] | 相同 | 相同 | 相同 |
| 蓝色「确定」按钮 bbox | 58394 px | **像素数相同** | 同 | 同 |
| 正文标记区差异 | 基准 | **0 px** | **0 px** | **0 px** |
| 「提示」标题字形区 | 基准 | **0 px** | **0 px** | **0 px** |

⇒ **`Msg` 空 = 弹窗空白；`Msg` 有串 = 显示该串。一一对应，无歧义。**
⇒ 弹窗是稳定停留（跨 37 秒逐像素不变），不是抖动。弹窗背后游戏仍在正常渲染轮播（四帧背景各不相同）。

### 第 2 步：真实上游的应答与我们完全不同

| 接口 | 我们伪造的 | 真实上游（7 次复测） |
|---|---|---|
| `state-api.bluearchive-cn.com/api/state` | 200 / 181 B JSON | **200 / 0 字节（空 body）**；`POST` 该路径 = 404，只有 GET |
| `gsqc-api.bluearchive-cn.com/api/state` | 同一份 181 B | 200 / 214 B，`application/json; charset=utf-8` |

真实 10 字段（`gsqc-api` 原文）：
```json
{"CallbackUrl":"","CustomerServiceUrl":"","AddressablesCatalogUrlRoots":null,
 "ResourceVersion":"","TableVersion":"","MediaVersion":"","PatchVersion":"",
 "State":0,"Msg":"platform id error","IsOpenPreDownload":false}
```

**我们缺**：`ResourceVersion` / `TableVersion` / `MediaVersion` / `PatchVersion` / `IsOpenPreDownload`
**我们多**：`Servers`（真实结构里不存在）

### 第 3 步：nginx 结构本身是错的
`ba_mitm.conf` 用**一个 server 块**兜住所有 `*.bluearchive-cn.com`，于是 `state-api` / `gsqc-api` / `static` 全部回同一份 JSON。而真实世界是**三个完全不同的后端**。

---

## 三、被本条定案一并排除的假设

| 假设 | 处置 |
|---|---|
| 系统 CA 未生效 | **已排除**。CA 生效时刻 = **01:33:45**（46 条 fatal `desc=49` 全部落在 01:24:58–01:33:45，之后归零；01:34:52 同一条 state-api 完整握手 + 200） |
| 证书链 / pinning | **已排除**。TLS 全线通过 |
| 客户端不发 SNI | **已排除**。上游完全靠 SNI 选证书；无 SNI 时 state-api→`*.certfallback.com`、gsqc→`*.unionpayintl.com`，主机名校验 62 处全 mismatch；未知 SNI 直接 `fatal alert 40` |
| `example.com` 可作上游参考 | **已排除**。A 记录就是 `<SERVER_IP>`（我们自己的机器），之前拿到的所有“上游应答”都是自己 nginx 的回响 |
| 网络不可达 / 进程崩溃 | **已排除**。无 crash、无 ANR、无 tombstone；无线程卡在 recv |
| `RetryUtils req_1/req_2` 是弹窗成因 | **已排除**。它的 5 次退避重试（2→4→8→16→32s）**晚于**弹窗出现，且每轮都一样，是独立进程（阿里云日志端点重试） |

---

## 四、当前正确的目标架构（已下达）

| 域名 | 应答 | 目的 |
|---|---|---|
| `state-api` / `stateqc-api` | **200 + 0 字节** | 与真实上游完全一致 |
| `gsqc-api` / `gs-api` | 200 + 真实 10 字段 JSON，`Msg:""`、`State:0` | 不弹窗，让客户端继续 |
| `static` | 暂留 404，**但必须记完整 URI 日志** | 观察客户端请求资产的路径与顺序 |
| 其余 | → `127.0.0.1:5000`（Shittim-Server） | 真正的私服实现 |

证书**必须**仍是 `<CERT_PATH>`（手机信任的是 `ca2/ca.crt`，1164 B）。切回 `ca3` 立刻复现 46 条 `alert 49`。

---

## 五、待解决的架构议题（暂缓，不与主线混）

手机侧是**按 uid 10576 + 443 端口全量劫持**，不是按域名。后果：
- `tapsdk.tapapis.cn` / `gid.tapapis.cn` / `openlog.tapapis.cn` / `*.log.aliyuncs.com` / `udata-api.open.yostar.net` 也被劫到我们这儿
- 客户端报 `Hostname ... not verified: DN=CN=*.bluearchive-cn.com`（**主机名不匹配**，不是链问题）
- 我们无法为第三方域名签证书

**候选方案：服务端 443 前置一层 nginx `stream` + `ssl_preread` 的 SNI 分流器**
- SNI 命中 `*.bluearchive-cn.com` / `example.com` → 转本地 8443（现有 MITM）
- 其它 SNI → 原始 TCP 透传到 `$ssl_preread_server_name:443`（真实公网）

**已排除的两条捷径**：
- hosts 改向：`/system/etc/hosts` 是只读 EROFS，`touch` 返回 `Read-only file system`
- 按 IP 白名单：`gsqc-api` 与 `udata-api.open.yostar.net` **共享同一组 IP**（`112.13.210.86` / `39.173.157.74` / `39.174.179.5`），按 IP 分流必然误伤

---

## 六、资产（static）的现实情况

- 当前 DNS 节点 `120.226.195.66` 回源 **403 AliyunOSS AccessDenied**（10/10）
- 旧缓存节点 `112.15.33.35` / `112.16.250.35` 曾回 200 的 **OSS 桶列表**（1000 条，`cbt1/AssetBundles/Android/*.bundle`，缓存快照 2026-10-18）
- `static` 是 TTL 4s 的调度型域名（`dma.tdnsdl1.cn`），这就是 200/403 忽好忽坏的原因

⇒ 后续若要真资产，走「反向代理到旧缓存节点」比「自己托管」现实得多。

---

## 七、红线（累计）

1. 判 TLS 通过**只认 pcap**：ServerFlight 之后是否出现应用数据 / `GET` / `POST` / `PRI *`。
2. `access_log` 有记录 ≠ TLS 通过；`error_log` 为空 ≠ TLS 通过。
3. **我们服务器上没记录 ≠ 客户端没发请求**（但本场景已由手机侧「全量按 uid 劫持」排除）。
4. tcpdump **不能用 `not src net 172.24.0.0/16`**（服务器自己在该网段，会把 ServerFlight 全滤掉）。
5. `ssl_certificate` 永远指向 `ca2/`，不得指向 `ca3/`。
6. 不给 `.so` 用 `cat > dst`。
7. `UseCustomExcel=true` 不得开启。
8. 探针实验**一次只改一个变量**，两个 conf 必须同步改。
