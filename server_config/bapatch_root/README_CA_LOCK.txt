# ============================================================================
#  CA LOCK —— 证书目录硬约束（写在服务端，防误切）
#  落点: /root/bapatch/README_CA_LOCK.txt
#  生成: 2026-11-14 01:47 CST（srv-ops）
# ============================================================================

## 一句话

**`ba_mitm.conf` 的 ssl_certificate 必须永远指向 `<CERT_PATH>`。**
切到 `ca3/chainS.crt` 会立刻回到「客户端 46 条 fatal alert 49 (access_denied)」的局面。

## 依据（实测，非推测）

| 项 | ca2（当前在用） | ca3（今晚早前） |
|---|---|---|
| 叶子 subject | `CN=*.bluearchive-cn.com` | `CN=*.bluearchive-cn.com` |
| 叶子 issuer | `CN=BA Test Root CA, O=BA` | `C=US,O=DigiCert Inc,...,CN=RapidSSL TLS RSA CA G1` |
| 根/锚 | `BA Test Root CA`（自签） | `RapidSSL TLS RSA CA G1`（伪装，自签） |
| 根证书文件 | `<CERT_PATH>` = **1164 B** | 无同名等价物 |
| 手机信任库 | **装的就是这份 1164 B PEM** | 未装 |

## 时间线证据（tls_min.pcap0，手机 → 我们）

- **01:24:58 – 01:33:45**：46 条明文 `fatal alert 49 access_denied`（TLS1.2 可读），
  按 SNI：`state-api` ×19、`stateqc-api` ×17、yostar/tap 系 ×10。
- **01:33:45** 之后：**0 条** alert。
- **01:34:52** 起：同一条 `state-api` 链路完整握手（CKE → CCS → Finished → 339 B 应用数据）→ **200**。
- 结论：**CA 生效时刻 = 01:33:45**，且生效后服务的是 ca2 的链。

## 硬约束（三条）

1. `ba_mitm.conf` / 任何新增 vhost 的 `ssl_certificate` → **只能** `<CERT_PATH>`
2. `ssl_certificate_key` → **只能** `<CERT_PATH>`
3. 改动这两个字段后，必须跑：
   ```sh
   echo | openssl s_client -connect 127.0.0.1:443 -servername state-api.bluearchive-cn.com 2>/dev/null \
     | openssl x509 -noout -subject -issuer
   # 期望 issuer 含 "BA Test Root CA"；若出现 "RapidSSL" → 立即回滚
   ```

## 已知的「看起来该改但其实不能改」的诱惑

- 觉得 `RapidSSL` 更"像官方"→ **不能换**。手机信任的是 `BA Test Root CA`，不是 RapidSSL。
- 觉得 ca3 的 serial 与官方一致更稳 → **不能换**。serial 不参与信任判定，锚才参与。

## 相关文件

- 分流器草稿：`/root/bapatch/sni-passthrough/`
- `/api/state` 探针备份：`ba_mitm.conf.probe1.*` / `example.com.conf.probe1.*`
- 日志字段备份：`0.ba_raw_format.conf.bak.*`
