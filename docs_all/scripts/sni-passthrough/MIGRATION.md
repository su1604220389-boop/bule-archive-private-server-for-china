# 迁移步骤（草稿，未执行）

> 核心约束：**stream 的 `listen 443` 和 http 的 `listen 443 ssl` 不能共存**，
> 必须同一次 reload 内完成「http 全部挪到 8443」+「stream 接管 443」。
> 任何一个漏改都会让 `nginx -t` 报 `duplicate listen options` 或抢端口失败。

## 0. 现状（01:46 实测）

```
nginx version: nginx/1.30.3
--with-http_v2_module --with-stream --with-stream_ssl_module
--with-stream_ssl_preread_module --with-http_realip_module --with-http_v3_module
（静态编译，无动态模块，无 /usr/lib/nginx/modules）
nginx.conf:7-13 已存在 stream{} 块，且 include /www/server/panel/vhost/nginx/tcp/*.conf（目录空）
```

## 1. http 层要改的 listen（**三个文件，一个都不能漏**）

| 文件 | 现在 | 改成 |
|---|---|---|
| `ba_mitm.conf:2` | `listen 443 ssl default_server;` | `listen 127.0.0.1:8443 ssl default_server;` |
| `example.com.conf:4` | `listen 443 ssl;` | `listen 127.0.0.1:8443 ssl;` |
| `example.com.conf:5` | `listen 443 quic;` | **保留不动**（UDP，见 RISKS 第 1 条） |
| `example.com.conf:3` | `listen 80;` | 保留不动 |
| `0.default.conf:4` | `listen 443 ssl ;` | `listen 127.0.0.1:8443 ssl ;` ← **最容易漏这个** |

> `0.default.conf` 是宝塔的默认站点，也占了 443。漏掉它，stream 抢不到 443。

## 2. 上线顺序（真实执行时的推荐序）

```sh
# ① 备份
TS=$(date +%s)
cd /www/server/panel/vhost/nginx
cp -a ba_mitm.conf            ba_mitm.conf.presni.$TS
cp -a example.com.conf   example.com.conf.presni.$TS
cp -a 0.default.conf          0.default.conf.presni.$TS
cp -a /www/server/nginx/conf/nginx.conf /www/server/nginx/conf/nginx.conf.presni.$TS

# ② 改 listen（三处 443→127.0.0.1:8443，quic 与 80 不动）
sed -i 's/listen 443 ssl default_server;/listen 127.0.0.1:8443 ssl default_server;/' ba_mitm.conf
sed -i 's/listen 443 ssl;/listen 127.0.0.1:8443 ssl;/'       example.com.conf
sed -i 's/listen 443 ssl ;/listen 127.0.0.1:8443 ssl ;/'    0.default.conf

# ③ 放分流器（用方案 B 的两级 map 版）
cp /root/bapatch/sni-passthrough/sni.conf /www/server/panel/vhost/nginx/tcp/99-sni-split.conf

# ④ 必须先测，再 reload
nginx -t && nginx -s reload

# ⑤ 验证三件事
ss -lntp | grep -E ':443 |:8443'
curl -skS --resolve state-api.bluearchive-cn.com:443:127.0.0.1 https://state-api.bluearchive-cn.com/api/state ; echo
curl -sS  -o /dev/null -w '%{http_code}\n' --resolve tapsdk.tapapis.cn:443:127.0.0.1 https://tapsdk.tapapis.cn/   # 应拿到真证书 200/404，而非我们的 CN
```

## 3. 回滚（一条命令级）

```sh
TS=<上线时的 ts>
cd /www/server/panel/vhost/nginx && \
cp -a ba_mitm.conf.presni.$TS ba_mitm.conf && \
cp -a example.com.conf.presni.$TS example.com.conf && \
cp -a 0.default.conf.presni.$TS 0.default.conf && \
rm -f /www/server/panel/vhost/nginx/tcp/99-sni-split.conf && \
nginx -t && nginx -s reload
```

## 4. 对 `/api/state` 两份的影响

把 `listen 443` 改 8443 **不改任何 location**，两份 `/api/state`（`ba_mitm.conf:27`、
`example.com.conf:85`）行为不变，`curl -H 'Host: ...' https://127.0.0.1/api/state` 的验证方式要改成
`https://127.0.0.1:8443/api/state`（或继续走 443 的 SNI 分流）。

## 5. 与当前探针实验的关系

本轮（`Msg=PROBE-M1-STATE-ZQ7`）**绝对不能动网络架构**，否则弹窗归因失效。
本文件只是草稿，未执行任何一条 sed。
