# 风险清单 —— SNI 透传分流器

按「上线后会打破什么」逐条列，每条给**实测依据**或**明确的不确定性**，不猜。

---

## 1. `listen 443 quic`（UDP）怎么处理

**现状**：`example.com.conf:5` 有 `listen 443 quic;`（UDP 443，宝塔默认开 h3）。
**分析**：
- stream 的 `listen 443` 是 **TCP**，与 UDP 443 不冲突，不需要动。
- 手机侧劫持规则是 `-p tcp --dport 443`，**UDP 不在劫持范围** → QUIC/h3 流量本来就直连真实服务器，不经过我们。
- 所以 `listen 443 quic` 保留即可，**但它是给 `example.com` 用的**：客户端对 `example.com` 若走 h3，会直连真实 `example.com`（我们自己的公网域名），打到我们公网 IP 的 UDP 443 → 仍是我们，证书是真证书，OK。

**建议**：保留，不动。若后续发现客户端对我们的 MITM 域名尝试 h3（因为 Alt-Svc），可在 `ba_mitm.conf` 加 `add_header Alt-Svc "";` 压制（目前 nginx 不主动发 Alt-Svc，风险低）。

---

## 2. 无 SNI 的连接（`$ssl_preread_server_name` 为空）

**实测**：01:42:19 抓到过一条 **无 SNI** 的连接（CH=1412，flight≈4023，afterB=234）。
**在分流器下**：`$ssl_preread_server_name` 为空 → map 走 `""` 分支。
- **建议：默认进 MITM（127.0.0.1:8443），不要拒绝。**
  理由：①拒绝会让客户端拿到 RST，表现为「网络错误」而不是「证书错误」，更难诊断；
  ②进 MITM 至少会拿到我们的证书，行为与今天完全一致，**不引入新变量**；
  ③stream 层没有 SNI 就等于没有任何分流依据，透传也无从下手（不知道连哪儿）。
- **不要**把它 `return` 掉或 `proxy_pass` 到空地址——stream 层 `return` 只支持 301/302 的 `ngx_stream_return`，用在 TCP 上会直接断连。

---

## 3. 客户端 IP 会不会丢

- **MITM 分支**：TCP 级代理，`$remote_addr` 仍是手机 IP（今天所有日志里的 `117.147.55.174` 会继续正确）。
  `ba_raw` 里的 `$remote_addr` / `$host` / `$http_user_agent` 都不受影响。
- **透传分支**：对我们只是 TCP 中继，我们不解析；对真实后端来说，源 IP 变成**我们服务器的 IP**。
  后果：第三方的风控/日志会看到我们；这不是功能问题，但是**把我们的 IP 暴露给第三方**。
- **`real_ip` 模块**：`--with-http_realip_module` 在，但本方案是 L4 透传，HTTP 层拿不到真实源 IP 的问题**不存在**（因为 MITM 分支就是真实源 IP）。**不需要配置 `real_ip_header`**。

---

## 4. `resolver` 与「透传分支」的失败模式

- 透传分支的 `proxy_pass $ssl_preread_server_name:443` 需要**运行时解析**，必须配 `resolver`（草稿用 119.29.29.29 / 223.5.5.5）。
- **失败模式**：DNS 挂了 → 该分支连不上 → 客户端表现为「网络错误」。今天这些域名是「证书错误」，两种错误对客户端来说都是失败，但**归因方式变了**，排查时要注意看 `/www/wwwlogs/sni_split.log` 的 `upstream=` 字段。
- `resolver` 不能写 `127.0.0.53`（systemd-resolved 的 stub，nginx 在 worker chroot 下常解析失败）。

---

## 5. 长连接被 `proxy_timeout` 切断

- stream 默认 `proxy_timeout 10m`。游戏网关是长连接，**必须显式放大**（草稿给 3600s）。
- 若客户端有心跳，10m 也不会断；但**不要赌**，直接 1h。

---

## 6. 谁还能连我们的 443（安全面）

- 分流器接管后，**任何**外部主机的 443 都能进来并被我们按 SNI 透传（或进 MITM）。
  这是「把服务器变成一个按 SNI 转发的 TCP 中继」——虽然只对携带合法 SNI 的 TLS 生效，但确实扩大了用途面。
- **缓解**：`stream` 层可以加 `allow/deny`，把来源限制在手机 IP（但手机 IP 会变，且经加速器）。
  建议：**先不加限制**，靠 `sni_split.log` 观测；若发现被扫，再加 `deny all; allow <手机网段>;`。

---

## 7. 与 `/api/state` 探针实验的冲突

- 迁移会改 `listen`，**任何 reload 都会打断正在进行的实验归因**。
- **硬规则：探针实验期间不动架构**（Lead 已定）。

---

## 8. `0.default.conf` 是隐形地雷

- 它 `listen 443 ssl ;`（注意分号前有空格），和 `ba_mitm.conf` 抢 443。
- 迁移时**必须一起改**，否则 `nginx -t` 直接失败：`duplicate listen options for 0.0.0.0:443`。
- 附带的**独立风险**（与本次迁移无关，但值得记）：只要它还在 443 上，
  任何落进 `server_name _;` 的流量都会拿到 `CN=default` **自签证书**，客户端必拒。

---

## 9. 回滚成本

- 低：三个 `cp -a` + 删一个文件 + reload。
- 但**回滚后那批第三方域名会重新被我们接管**，`Hostname not verified` 会回来。属预期。

---

## 10. 未验证项（诚实标注）

1. 两级 `map` 在 stream 层的 `~^1:` 正则匹配行为**未在本机实测**（需 `nginx -t` 阶段验证）。
2. `$ssl_preread_server_name` 在 ClientHello 被 TCP 分片跨段时，nginx 会缓存直到读全（`ssl_preread` 内部缓冲），
   但**大于 `proxy_buffer_size` 的 ClientHello 会失败**——草稿给 16k，实测最大只见过 1561 B，余量足够。
3. QUIC 之外的 HTTP/3 fallback 行为未测（我们没开 h3）。
