# 免 root 客户端观察记录（滚动）— 起始 2026-11-18 00:06

**只读观察**：未改配置、未 reload/restart、未动证书/WAF/MySQL、未 curl 客户端路径。

## 0) 客户端将使用的地址
```
sdk_url           = https://example.com/sdk
ServerInfoDataUrl = https://example.com/api/state
```
直连真实 LE 证书打 443（不经 DNS 劫持、不经 MITM，公网侧 `ssl_verify_result=0` 已验证）。

---

## ① 日志文件名（已确认）
```
access_log  /www/wwwlogs/example.com.log        ← 13,446,698 B，最后写入 Nov 18 00:01
error_log   /www/wwwlogs/example.com.error.log  ← 2,872,124 B，Nov 17 21:54
（同一文件被两个 server 块共用：:154 和 :184）
```
**⇒ 要盯的就是 `/www/wwwlogs/example.com.log`。**

## ② Shittim 进程 / tmux（都在）
```
root 2656526  ... /root/dotnet10/dotnet …/Shittim-Server.dll --console --id 2   （Nov17 起）
tmux: shittim: 1 windows (created Tue Nov 17 23:08:19 2026)
端口: 5000 / 5100 / 6667 全部 LISTEN（同一 pid）
```

## ③ sdkcard 与桥（都在）
```
2632769 /usr/bin/python3 /www/wwwroot/ba_sdk/sdkcard.py        8080 LISTEN（127.0.0.1）
2651206 python3 account_auth_probe.py                           9097 LISTEN（127.0.0.1）
```

## ④ 已启动只读抓取（非侵入）
```
/tmp/noroot_watch_000613.log     （grep 过滤：/api/state|/api/gateway|/sdk/|/common/|/user/|/heartbeat/|/order/）
进程：timeout 1800 tail -n 0 -F /www/wwwlogs/example.com.log   (pid 2660252 / tail 2660255)
时效：**30 分钟，约 00:36 自动结束**（需要更久我再起一个）
当前内容：0 字节（自 00:06 起还没有匹配请求）
```

---

## 核心问题的**静态预判**（尚未有客户端请求，先给依据）

**sdkcard.py 实际只认"不带 /sdk 前缀"的路径：**
```
/common/config      -> 返回真实的 SDK 配置（检测地址改指我们）
/user/login         -> OpenID 字段即卡密
/user/quick-login   -> 已绑定设备放行
/user/detail
/heartbeat/pulse
/order/products|create|detail
（do_POST = do_GET，路由判定用 path == '/common/config' 这种**全等比较**）
```
**nginx 侧是"带前缀转发、去前缀"：**
```nginx
location /sdk/ {  proxy_pass http://127.0.0.1:8080/;  }   ← 末尾有 /，所以 /sdk/common/config → 上游 /common/config
```
**⇒ 两种客户端行为都不会 404：**
| 客户端实际请求 | 命中 nginx | 到达 sdkcard | 结果 |
|---|---|---|---|
| `https://example.com/sdk/common/config` | `location /sdk/` | `/common/config` | **200**（推荐形态） |
| `https://example.com/common/config`（丢掉 `/sdk`） | `location ^~ /` → **Shittim:5000** | Shittim 无此路由 | **404**（就是 Lead 担心的那种） |
**⇒ 所以判据就是访问日志里出现哪一条；一旦出现 `/common/config`（不带 `/sdk/`），说明前缀被丢弃，需要 Lead 给方案（我不改 nginx）。**

## 已有旁证（非本轮客户端）
```
sdk.log 尾：00:00:57 /common/config dev=   BODY {}      ← 00:00 有一次 /common/config 到达 sdkcard
                （说明 nginx /sdk/ → 8080 这条转发链是通的）
访问日志尾：00:01:44 "GET /api/state HTTP/1.1" 200 64 curl/8.22.0   （来自 127.0.0.1）
             00:01:41 "GET / HTTP/1.1" 200 2 curl/8.22.0
```

---

## 待采集（用户启动后）
1. 访问日志里 `/api/state`、`/sdk/...` 的**首行**（含 UA、来源 IP、状态码）
2. sdkcard `sdk.log` 是否出现 `dev=` 与卡密
3. Shittim stdout（`tmux capture-pane -p -t shittim -S -400 | tail -80`）
4. 桥日志（`api_all_requests.log`）里是否出现 `/api/account/*`
5. 判定：**`/sdk/common/config` 还是 `/common/config`**
