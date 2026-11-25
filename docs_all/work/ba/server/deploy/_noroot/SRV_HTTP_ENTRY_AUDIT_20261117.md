# HTTP 明文入口盘点（无 root 客户端前置调查）— 2026-11-17 23:59

**只读盘点**：未写任何配置、未 reload/restart、未动证书 / WAF / MySQL。
本轮 curl 总数 = **2**（间隔 3 s，无 444）。

---

## ① 有没有 `example.com` 的 vhost —— **有，而且同时监听 80 与 127.0.0.1:8443(ssl)**

文件：`/www/server/panel/vhost/nginx/example.com.conf`（4,461 B 级，宝塔生成 + 手工追加块）

```nginx
server {
    listen 80;                       # ← 明文 HTTP 入口，全局 0.0.0.0
    listen 127.0.0.1:8443 ssl;       # ← SNI 分流后走这个（MITM 链路）
    http2 on;  http3 on;
    server_name example.com example.com;
    root /www/wwwroot/example.com;
    ...
    location = /api/state  { root /www/wwwroot/bapatch/noroot_payloads; rewrite ^ /state1.json break; }
    location = /checkhealth.html { return 200 "ok"; }
    location = /api/health { return 200 '{"status":"ok"}'; }
    location = /          { return 200 "ok"; }              # ← 根路径直接回 "ok"
    location ^~ /         { proxy_pass http://127.0.0.1:5000; ... }   # ← 其余全部打到 Shittim
    location /sdk/        { proxy_pass http://127.0.0.1:8080/; ... }  # ← SDK 打 sdkcard.py
}
# 另有第二个 server（仅 127.0.0.1:8443 ssl）server_name example.com
#   location = /api/state → state2.json ；location / → 404
```

**关键点**
- **80 端口上有这个站**：`location ^~ /` 把任何路径转给 `127.0.0.1:5000`（Shittim），`/api/state` 走静态文件，`/sdk/` 走 8080。
- **`www.` 与裸域共用同一个 server 块**（`server_name example.com example.com;`），所以 http 明文打 `www.` 也落在同一处。
- **`add_header Strict-Transport-Security` + `error_page 497 https://$host$request_uri`**：HSTS 头只在 https 响应里发；497 只对"https 打到 http 端口"生效，**不影响纯 http 明文请求**。

## ② 80 在监听吗、指向哪 —— **在监听；由 nginx(pid 2911) 的 worker 处理，落到上面那个 vhost**

```
LISTEN 0.0.0.0:80    users:(("nginx",pid=2659425),("nginx",pid=2659424),("nginx",pid=2911))
LISTEN 0.0.0.0:443   users:(("nginx",...2911))
LISTEN 0.0.0.0:8081  users:(("nginx",...2911))     ← 卡密面板
LISTEN 0.0.0.0:5000  users:(("dotnet",pid=2656526))  ← Shittim API
LISTEN 0.0.0.0:5100  (dotnet 2656526)                ← Shittim Gateway
LISTEN 0.0.0.0:6667  (dotnet 2656526)                ← 游戏 TCP
LISTEN 127.0.0.1:8080 (python3 2632769)              ← sdkcard.py
LISTEN 127.0.0.1:9097 (python3 2651206)              ← 桥 account_auth_probe
```
其它 80 站点：`0.default.conf`（`listen 80; server_name _;`）、`phpfpm_status.conf`（`listen 80; server_name 127.0.0.1;`）；
**`<SERVER_IP>.conf` 是 8081（卡密面板）**，`ai_example_tech.conf` 是 **8880**，都不占 80。

## ③ 两个 curl（本轮唯一两次）

```
HOSTTEST  code=200     （curl -H 'Host: example.com' http://127.0.0.1/）
LOCAL5000 code=404     （curl http://127.0.0.1:5000/api/state）
```
- **HOSTTEST=200**：http 80 + 该 Host → 命中 `location = /` 的 `return 200 "ok"` ⇒ **http 入口通**。
- **LOCAL5000=404**：Shittim 本身**没有** `/api/state` 路由（该路径由 nginx 静态文件提供），属正常，不是故障。

## ④ SDK 服务在不在 —— **在（127.0.0.1:8080，仅本机）**

```
LISTEN 127.0.0.1:8080  python3 pid 2632769
cmdline: /usr/bin/python3 /www/wwwroot/ba_sdk/sdkcard.py
目录 /www/wwwroot/ba_sdk/：cards.json(189 B, 23:59)  sdkcard.py(13,328 B)  sdk.log(22,573 B, 23:08)
nginx 侧：example.com.conf:160 `location /sdk/ { proxy_pass http://127.0.0.1:8080/; }`
```
桥：`python3 account_auth_probe.py` pid 2651206（9097）。
Shittim：pid 2656526，5000/5100/6667。

## ⑤ 要让「http 明文客户端」真正跑通，还缺什么（**只描述，未动手**）

1. **state 里的 URL 还是 `https://`**
   - `state1.json`（80 端口那条 `/api/state` 用的）内容：
     ```json
     {"Servers":["https://example.com/api/"],"State":1,"Msg":""}
     ```
     ⇒ `Servers` 是 **https**。若客户端要全程明文，这里得给一份 **http://** 的 payload（并让 80 的 `location = /api/state` 指向它）。
   - `state2.json`（8443/www 用）里 `AddressablesCatalogUrlRoots` 也是三条 **https://static...**。
2. **客户端侧的 CDN / 资源地址**仍指向 `https://static*.bluearchive-cn.com/prodm39`，无 root 方案若也改资源域，需要另备 http 源（当前 `static*` 走 443 SNI 分流，80 上没有 static 站）。
3. **`/sdk/` 的 `X-Forwarded-Proto` 写死为 `https`**（example.com.conf:167）——明文访问时 sdkcard 会以为自己是 https；若 SDK 要用 `X-Forwarded-Proto` 生成回调/校验地址，需要按 `$scheme` 传（**改配置，需授权**）。
4. **HSTS 头**（`add_header Strict-Transport-Security`）：只影响 https 响应，明文无影响；但若客户端以前收过 HSTS，浏览器类请求可能被强制升级 —— **原生客户端不受此限**。
5. **WAF**：`free_waf.conf` 是全局 `access_by_lua_file`，**80 端口同样受它管**。本轮限速下 200 正常；但高并发（游戏登录会打多个协议）仍可能触发 `cc` 限流（120 req/60s → 444）。无 root 方案上线前建议给该入口单独放宽或加白（**改 WAF，需授权**）。
6. **80 没有 `location /api/` 的专门转发**（除 `/api/state`、`/api/health`），其余 `/api/*` 都吃 `location ^~ /` → 5000，这正好是 Shittim 的 `/api/gateway`，**通道本身已经通了**。
7. **卡密面板在 8081**，与 http 客户端方案无关，不要混。

## 附：一处现场变化（非我所为，仅记录）
```
nginx master pid 2911 启动于 Nov 13 13:08；但 worker 是 pid 2659424/2659425（23:55 左右）
⇒ 23:55 前后有人 reload/重启过 nginx（不是我，本轮只读）
/www/server/nginx/conf 目录 mtime = 23:55
```

## 本轮限速与红线
```
curl 次数 = 2（HOSTTEST + LOCAL5000），间隔 3 s；无 444
未写任何文件到服务器（报告写在本机）
未 reload/restart、未动证书 / WAF / MySQL / 宝塔面板
```

---

# § 预备：SDK 前缀兜底方案（**未应用**）

数据采集时间：2026-11-18 00:14 ｜ 全程只读（只打 127.0.0.1，不经 nginx，不碰 WAF）

## ① 各路径在 5000（Shittim）与 8080（sdkcard）上的实际状态码

```
路径                  :5000 (Shittim)   :8080 (sdkcard)
/common/config        -> 404             -> 200
/common/geo-ip        -> 404             -> (未测)
/user/login           -> 404             -> 200
/user/quick-login     -> 404             -> (未测)
/user/detail          -> 404             -> (未测)
/heartbeat/pulse      -> 404             -> 200
/order/products       -> 404             -> 200
/order/create         -> 404             -> (未测)
/order/detail         -> 404             -> (未测)
```
**⇒ 5000 上这些前缀全部 404（Shittim 完全没占）；8080 上全部 200。⇒ 把这几个前缀转给 8080 是安全的，不会抢走 Shittim 的任何路由。**

## ② Shittim 有没有同名路由
```
grep -rn --include=*.cs -E '"/(order|user|common|heartbeat)' /www/wwwroot/ba_srv/   → 无输出
grep -rn --include=*.cs -E '\[Route\("' /www/wwwroot/ba_srv/                        → 无输出
```
**原因**：服务器上**只有编译后的 DLL**（`/www/wwwroot/ba_srv/Shittim-Server.dll`），**没有 .cs 源码**，所以 grep 不出东西。
**⇒ 结论以 ① 的运行时实测为准：Shittim 没有 `/common/`、`/user/`、`/heartbeat/`、`/order/` 路由（全 404）。**

## ③ 可粘进宝塔的配置片段（**未应用**）

**位置**：`/www/server/panel/vhost/nginx/example.com.conf` 的第 1 个 server 块内，
**建议紧贴在现有 `location /sdk/ { ... }`（第 160 行）之后、`}` 之前**；
或放在 `location ^~ / {`（第 100 行）**之前**（可读性更好）。

```nginx
    # ---- BAPATCH-SDKFALLBACK v1: 客户端丢了 /sdk 前缀时的兜底（未应用）----
    location = /common/config {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Connection "";
    }
    location ^~ /common/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Connection "";
    }
    location ^~ /user/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Connection "";
    }
    location ^~ /heartbeat/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Connection "";
    }
    location ^~ /order/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Connection "";
    }
    # ---- BAPATCH-SDKFALLBACK v1 END ----
```

**关于结尾斜杠（重要）**：这里用 `proxy_pass http://127.0.0.1:8080;`（**不带**结尾 `/`）——
不带结尾斜杠时 nginx **原样透传完整 URI**，`/user/login` 到上游仍是 `/user/login`；
若写成 `http://127.0.0.1:8080/;`（带 `/`），nginx 会**把匹配到的 location 前缀替换掉**，`/user/login` 会变成 `/login`，sdkcard 就会 404。
（现有 `/sdk/` 用的是带 `/` 的写法，正是为了剥掉 `/sdk` 前缀 —— 两者目的相反，别照抄。）

**`X-Forwarded-Proto`**：这里固定 `https` 是**沿用现有 `/sdk/` 的写法**（SDK 会用它拼回调地址）。
如果无 root 客户端确实全程 http，建议改成 `$scheme`；但这属于行为变更，**需授权后再动**。

## ④ nginx 匹配优先级（确认 `= /common/config` 不会被 `^~ /` 吃掉）

**结论：能命中，不会被子吃掉。** 依据 nginx 官方 `location` 匹配规则（`ngx_http_core_module`）：

1. 先做**精确匹配** `location = /uri`：**一旦命中，立即结束，不再看其它**；
2. 否则找**最长前缀**；若该最长前缀带 `^~`，**跳过正则**，直接用该前缀块；
3. 再否则按配置顺序试 `~` / `~*` 正则，命中即用；
4. 最后回落到第 2 步记住的最长前缀块。

**⇒ 两条都成立：**
- `location = /common/config` 命中的是**第 1 步**，`^~ /` 根本没机会参与；
- `location ^~ /user/` 与 `location ^~ /` 都是前缀，**按最长前缀匹配**，`/user/`（7 字符）> `/`（1 字符）⇒ 命中 `/user/`；`^~` 只影响"是否再试正则"，不改变"最长前缀优先"。

## ⑤ 生效方式（**必须走宝塔，不要 SSH 手改**）

```
宝塔面板 → 网站 → example.com → 设置 → 配置文件
  → 把上面的片段粘到 location ^~ / { 之前（或 /sdk/ 之后）→ 保存
  → 宝塔会自己 reload nginx
```
**注意**：宝塔保存时会重写 `server_name` / `ssl_certificate*` 等行，但**手工追加的 `location` 块此前实测能存活**（本文件 §基线 已记录）。

## ⑥ 逐条回滚

```
删掉以 "# ---- BAPATCH-SDKFALLBACK v1:" 开头、到 "# ---- BAPATCH-SDKFALLBACK v1 END ----" 结尾的整段（共 5 个 location 块）
→ 保存即可；无需重启，宝塔会 reload。
```

## ⑦ 风险提示

- 加了 `/user/`、`/order/`、`/heartbeat/`、`/common/` 之后，**这几个前缀在 80 和 443 上都不再走 Shittim**。当前实测它们全是 404，所以无副作用；**但若将来 Shittim 增加同名路由，会被这段抢走**。
- 这段**不解决 `/sdk` 前缀丢失的根因**，只是兜底。根因在客户端 `sdk_url` 的拼法。
