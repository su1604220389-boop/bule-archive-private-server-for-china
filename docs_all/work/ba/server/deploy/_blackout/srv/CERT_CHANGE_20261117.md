# 证书更换影响核查（只读）

- 执行者：srv-ops
- 时间：2026-11-17 20:44（北京时间 UTC+8）
- 触发：用户在宝塔面板给「反向代理」项目换了证书（显示 89 天到期）
- 本次**未改任何东西**（无 nginx reload、无配置写、无 DLL/桥改动）

---

## 结论（三句）

1. **换的是 (a)：只有 `example.com` 的证书被换**（Let's Encrypt `YR1`，notBefore 2026-11-17 11:43:05Z、notAfter 2027-02-15 11:43:04Z ≈ **90 天**）。`ba_mitm.conf`（`*.bluearchive-cn.com` 的 MITM）**文件 mtime 仍是 2026-11-16 05:52，未被碰**。
2. **MITM 那条路没有被破坏**：8443 上 `gsqc-api.bluearchive-cn.com` 拿到的仍是 **我们自签 CA** 签的 `CN=*.bluearchive-cn.com`（issuer `CN=BA Test Root CA, O=BA`，notAfter **2029-02-15**），SAN 含 `*.bluearchive-cn.com` / `bluearchive-cn.com` / `state-api` / `gsqc-api` / `gs-api` / `static`。
3. **服务没有受影响**（三跳全通、桥活着、游戏 API 200），**但有一处真实回归：新证书 SAN 只有裸域，没有 `www.`** —— `https://example.com/` 现在**证书校验失败（curl code=000）**。这是本次换证书**唯一**的副作用，需要你决定是否让用户重新签一张含 `www` 的。

---

## ① 换的是哪张证书 / 哪个 vhost

```
/www/server/panel/vhost/nginx/ba_mitm.conf:17/53/107   ssl_certificate <CERT_PATH>      ← MITM，未改
/www/server/panel/vhost/nginx/example.com.conf:21   .../cert/example.com/fullchain.pem
/www/server/panel/vhost/nginx/example.com.conf:179  .../cert/example.com/fullchain.pem   （www 块，同一张）
/www/server/panel/vhost/nginx/0.default.conf:11          .../cert/0.default/fullchain.pem
```
```
目录 mtime：
  cert/example.com/   Dir 2026-11-17 20:43   fullchain.pem 5,673 B  20:43
                                            privkey.pem   1,703 B  20:43
  cert/ba_mitm/            全部 2026-11-13 18:58（未动）
  cert/0.default/          全部 2026-08-26 12:21（未动）
conf mtime：
  example.com.conf   2026-11-17 20:43:17   ← 被宝塔重写（换证书时自动改）
  ba_mitm.conf            2026-11-16 05:52:04   ← 未动
```
**⇒ 判定 (a)。**

## ② 三处 TLS 实测

| 目标 | subject / issuer | 有效期 | SAN |
|---|---|---|---|
| `8443` + `gsqc-api.bluearchive-cn.com` | `CN=*.bluearchive-cn.com` / **`CN=BA Test Root CA, O=BA`** | 2026-11-13 → **2029-02-15** | `*.bluearchive-cn.com`, `bluearchive-cn.com`, `state-api`, `gsqc-api`, `gs-api`, `static` |
| `8443` + `example.com` | `CN=example.com` / **Let's Encrypt YR1** | 2026-11-17 → 2027-02-15 | **仅 `example.com`** |
| `443` + `example.com` | 同上（同一张） | 同上 | **仅 `example.com`** |

**判据对照**
- `gsqc-api` 那张**仍是自签 CA** ✅（没有变成公网 CA）
- `example.com` 是公网 CA（Let's Encrypt）✅
- **SAN 缺 `www`** ❌ —— 与你的判据不符，且是**从旧证书退化的**（旧证书 SAN 含 `www.`）

## ③ nginx 语法 / 错误日志

```
nginx -t : syntax is ok / test is successful
nginx_error.log 最后一条业务相关：2026-11-10 09:21（扫描器 SSL 乱码），**今天无新增**
tcp-error.log   最后三条：20:33–20:34 upstream timed out → 208.43.170.231:443（WorldRaid coordinator，与证书无关）
               20:02 有一条客户端 reset by peer（39.182.87.249 → 124.239.14.252，正常网络抖动）
tcp-access.log  grep failed|handshake|error → **无输出**
```
**⇒ 换证书后没有新的 TLS 报错。**

## ④ 端到端（20:44）

```
https://example.com/api/state             200   64 B     ✅
https://example.com/api/gateway  POST {}  400   20 B     ⚠️ 空 body 的协议错误（改证书前也是这个行为，非回归）
https://example.com/sdk/common/config     200   7,838 B  ✅
game api (--resolve gsqc-api → 127.0.0.1)      200   2 B      ✅
https://example.com/api/state         **000**  0 B  ❌ 证书校验失败
```

## ⑤ 桥接 / 后端

```
curl 127.0.0.1:9097/api/health → 200
LISTEN 5000 (dotnet pid 2635890) / 9097 (python3 pid 2633742) / 9098 (python3 pid 44279)
tcp-access 最近 5 条：全部 `TCP|200`，含 sni=gsqc-api 与 sni=example.com，无失败记录
```

## ⑥ nginx 进程 / vhost 完整性

```
master  2911   Fri Nov 13 13:08:36 2026   ← 未重启
worker  2637051/2637052/2637053  Tue Nov 17 20:43:18 2026   ← **20:43:18 reload 换的新 worker**
nginx -T: server_name 19 个，server 块 7 个
```
**⇒ 用户换证书触发了一次**graceful reload**（master 没换、worker 轮换），vhost 数量正常（7 块 / 19 个 server_name）。**

---

## 需要你裁决的一件事（我没有改）

**`example.com` 的证书校验现在失败**：
- 该 server 块（`example.com.conf:177-180`）用的就是这张**只含裸域**的证书；
- 之前那张 SAN 含 `www.`，所以 `www` 是可用的；**换证后退化**；
- 影响面：只有 `www.` 这个入口（`state2.json` 那条）。**游戏主链路（`*.bluearchive-cn.com` / 裸域）不受影响。**

**建议（不执行）**：在宝塔重新签一张 **同时包含 `example.com` 和 `example.com`** 的证书（DNS 验证时把 `www` 也勾上），再 reload 即可；或者接受 `www` 入口失效。

---

## 附：本次只读
```
未 reload / 未 restart nginx
未改任何 .conf / .pem
未改桥 / DLL / 数据库
新增：仅本报告
```
