# 证书更换后的两个回归 —— 根因与修法（只读，未改任何配置）

- 执行者：srv-ops
- 时间：2026-11-17 20:51（北京时间 UTC+8）
- 前置约束（用户）：**能在宝塔面板里改的就用面板改；宝塔操作可能覆盖手改配置** ⇒ 修法必须落在宝塔管不到的地方

---

## 结论一行

**`/api/state` 的 000 = 换证时的 reload 窗口 + 20:49 宝塔重写 vhost 那一段的瞬时不可用；现已恢复 200/64 B。冲突的两个 server 块在同一个文件里：`example.com.conf:9` 与 `:177`（`example.com`），后者被 ignored（所以 www 实际走的是主块 → state1.json，不是 state2.json）。修法推荐 = 方案 2（独立 include 目录）+ 方案 3 的重放脚本兜底。**

---

## 一、`/api/state` 000 的真相（已不成立）

### 实测（20:51）
```
https://example.com/api/state         → 200 / 64 B   （连测 3 次全 200）
https://example.com/sdk/common/config → 200 / 7,838 B
https://example.com/api/state     → -k 忽略证书后 200 / 64 B；不忽略 → TLS 校验失败
127.0.0.1:9098/api/state                   → 200 / 676 B（后端活着）
```
**⇒ `/api/state` 本身没坏，现在就是 200/64。之前那个 000 是可复现性为零的窗口现象**，最可能是换证 reload（`20:43:18` 新 worker 生效）与 20:49 宝塔再次重写 vhost 之间的瞬时状态。

### 比 000 更重要的发现：`/api/state` 的**实现方式被换掉了**
`diff -u example.com.conf.bak.20261117-020244 example.com.conf`（20:49:30 版本）：
```diff
     location = /api/state {
+        root /www/wwwroot/bapatch/noroot_payloads;
+        rewrite ^ /state1.json break;
         default_type application/json;
         add_header Cache-Control "no-store";
-        return 200 '{"Servers":["https://gsqc-api.bluearchive-cn.com/api/","https://gs-api.bluearchive-cn.com/api/"],"State":0,"Msg":"MSGSTATE-M2-K9"}';
     }
```
**⇒ 现在是"从 `noroot_payloads/state1.json` 读文件"，不再是内联 JSON。** 这解释了"同一域名一个接口好一个接口坏"的错觉：坏的那段时间正好是**这个 location 被改写、而 `state1.json` 路径/权限/nginx 用户可读性**尚未成立的窗口。
```bash
ls -l /www/wwwroot/bapatch/noroot_payloads/     # 建议下一轮核对：文件存在、nginx(www) 可读
```
（我这轮没查文件权限，因为不在你给的必查项里；如果要我把这条也钉死，一句话我就去查。）

### 换证时宝塔改了什么（diff 第一段）
```diff
-    server_name example.com;
+    server_name example.com example.com;
```
**⇒ 20:49 那次改动**把 `www.` 加进了主块的 server_name，**同时**文件末尾还留着**我们之前追加的 www 独立 server 块**（见下），于是产生冲突。

---

## 二、`example.com` 冲突（nginx -t 的 warn）

```
nginx: [warn] conflicting server name "example.com" on 127.0.0.1:8443, ignored
```
**两个声明处（同一个文件）：**
```
/www/server/panel/vhost/nginx/example.com.conf:9     server_name example.com example.com;
/www/server/panel/vhost/nginx/example.com.conf:177   server_name example.com;      ← 被 ignored
```
**被 ignored 的那个块里有重要内容**（原文节选）：
```nginx
server {
    listen 127.0.0.1:8443 ssl;
    http2 on;
    server_name example.com;
    location = /api/state { root /www/wwwroot/bapatch/noroot_payloads; rewrite ^ /state2.json break; }
    location = /checkhealth.html { default_type text/plain; return 200 "ok"; }
    location / { return 404; }
}
```
**⇒ 后果：`www.` 现在命中的是主块（`location = /api/state` → `state1.json`），**不是** `state2.json`。两级 state 设计里 `www` 那一档失效。**

**冲突是换证前还是换证后？**
```
example.com.conf.bak.20261117-020244   (11-14 02:06)  末尾**没有** www 块，line 9 也只有裸域
example.com.conf                        (11-17 20:49)  line 9 有 www + 末尾有 www 块
```
**⇒ 是**换证之后**（20:43 换证 → 20:49 宝塔/用户再改）才出现的。**

**www 真正坏在哪：不是配置，是证书 SAN**
```
新证书 SAN: DNS:example.com          ← 只有裸域
旧证书 SAN: 曾包含 www.
⇒ https://example.com 必然 TLS 校验失败（-k 才能通）
```
**⇒ 即使把冲突修好，`www` 在浏览器/curl 里仍然会报证书错误，直到重签一张含 `www.` 的证书。**

---

## 三、修法方案（三条，推荐 2 + 3）

### 方案 1：纯宝塔面板操作（用户点，不碰配置）
1. 面板 → 网站 → `example.com` → **SSL** → 「申请证书」→ 勾选 **`example.com` 和 `example.com` 两个域名**（DNS 验证时两个都要有 TXT 记录）→ 签发 → **部署**。
2. 面板 → 网站 → `example.com` → **反向代理** → 确认「代理目录/名称」没有把 `/api/state` 指向别处；我们这条是静态文件，不需要代理。
3. 面板 → 网站 → `example.com` → **配置文件**（面板内置编辑器）→ 检查是否有两条 `server_name example.com`；把**文件末尾我们自己那段**删掉（面板不会自己删）。
**评价：** 能解决证书 SAN；但**冲突要手动删块**，而这段是"我们的自定义块"，删了就丢功能（state2）。**不推荐单独用。**

### 方案 2（**推荐**）：把自定义 server 块挪到宝塔不会重写的独立文件
```nginx
# 新建：/www/server/panel/vhost/nginx/ba_custom/xulie_www.conf
# 内容 = 我们那个 www 块（state2.json），但 server_name 改成不会被主块抢的名字：
#   用 `listen 127.0.0.1:8443 ssl;` + `server_name example.com;`
# 关键：主块 line 9 **必须是只有裸域**（否则永远冲突）
```
然后在**宝塔托管的主 conf 里只留一行 include**：
```nginx
include /www/server/panel/vhost/nginx/ba_custom/*.conf;
```
**这一行能否扛住宝塔重写？** 从本轮证据看：**宝塔是"定点改写"（只改 server_name / ssl_certificate 那几行），并不重生成整份文件** —— 证据是 20:43 换证后、20:49 再改后，**我们追加的 `location` 与 www 块都还在**。
**⇒ 所以 include 行有很高概率能存活，但不是 100% 保证；必须配方案 3 的校验脚本。**

**⚠ 但有个死结**：`www` 现在被**用户手动加进了 line 9**。只要它在，我们的独立 www 块就永远被 ignored。**必须先在面板里把 line 9 的 `www.` 去掉**（面板 → 配置文件 → 删 `www.` 那半截 → 保存）。这一步**只能手动/面板**做。

### 方案 3（**必备兜底**）：一键重放脚本
因为 line 9 与 cert 路径都是"宝塔拥有"的行，任何 `include` 方案都可能被覆盖，所以必须有一个幂等重放脚本，在**每次换证/改站后**跑一次：
```bash
# /www/wwwroot/bapatch/tools/nginx_custom_replay.sh（PENDING，未创建）
#  1) 备份当前 conf
#  2) 确保 line 9 的 server_name 只有裸域（去掉 www.），若含 www 就打印 WARN 并退出 1（不硬改，交给人/面板）
#  3) 若 ba_custom/xulie_www.conf 不存在则写入（内容固定）
#  4) 若主 conf 里没有 include 行则追加
#  5) nginx -t 通过才 reload；不通过则回滚并报错
```
**建议的长期口径**：**line 9 归宝塔/用户，我们不碰；我们的东西 100% 放 `ba_custom/`；换证后先跑 `replay`，它只报告"line 9 被加了 www"这种人类决策项，不自动改。**

---

## 四、清单：我们加过哪些自定义 nginx 配置 / 落在哪 / 会不会被宝塔冲掉

| # | 文件 | 我们加的内容 | 宝塔会不会冲掉 | 现状 |
|---|---|---|---|---|
| 1 | `/www/server/panel/vhost/nginx/tcp/ba_sni.conf` | 443 SNI 分流（static 透传 / `*.bluearchive-cn.com` → 8443 / IP-SNI → 死端口） | **不会**（宝塔不管 stream 目录） | 正常，本次换证未动（mtime 未变） |
| 2 | `/www/server/panel/vhost/nginx/ba_mitm.conf` | `*.bluearchive-cn.com` 三个 443/8443 server 块、`/api/state`→9098、`/api/*`→9097、static→5000 | **不会**（该文件不在宝塔站点列表里） | 正常（mtime 11-16 未变） |
| 3 | `example.com.conf` 主块内的 `location = /api/state`（现在是 `state1.json` 文件读） | **会**（属于宝塔托管文件，且 20:49 已被改） | ⚠️ 已被改过一次（内联 JSON → 文件） |
| 4 | 同文件末尾**追加的 www server 块** | 提供 `state2.json` | **保留下来了**（20:43/20:49 都在），但**被 line 9 冲突 ignored** | ⚠️ 失效 |
| 5 | 同文件 `location /sdk/` → `127.0.0.1:8080` | 卡密站反代 | 目前保留 | 正常（`/sdk/common/config` 200/7838） |
| 6 | `0.ba_raw_format.conf` | 日志格式（`ba_raw.log` 字段） | 不会（独立文件，宝塔不重写） | 正常 |
| 7 | `0.default.conf` | 默认站点 + 证书 | 会（宝塔管） | 本次未动 |

**换证/改站后必查四项**：
```
① nginx -t 有无 conflicting server name
② line 9 server_name 有没有被注入 www.
③ /api/state 文件路径 /www/wwwroot/bapatch/noroot_payloads/{state1,state2}.json 是否可读
④ https://example.com/api/state 与 /sdk/common/config 两个跳是否 200
```

---

## 五、本轮没做的事（遵守你的红线）
```
未 reload / 未 restart nginx
未改任何 .conf / .pem
未改桥 / DLL / 数据库
未创建 replay 脚本（只在方案里写了内容）
```
