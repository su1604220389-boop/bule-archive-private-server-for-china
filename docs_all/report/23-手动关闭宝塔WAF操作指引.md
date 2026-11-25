# 手动关闭宝塔「Nginx免费防火墙」操作指引

> 本文档只描述**用户手动操作**步骤。任何自动化程序/agent 均不得执行本文中的操作。
> 生成时间：2026-11-14 03:0x
> 服务器：<SERVER_IP>

---

## 0. 先说清楚我们要关的是什么

服务器上装的不是常见的 `btwaf`（`/www/server/btwaf` 目录不存在），而是：

| 项 | 实测值 |
|---|---|
| 面板名称 | **Nginx免费防火墙** |
| 插件标识 | `free_waf`（版本 8.3，分类「系统工具」） |
| 插件目录 | `/www/server/panel/plugin/free_waf/` |
| 运行目录 | `/www/server/free_waf/` |
| 全局总开关 | `/www/server/free_waf/config.json` → `"open": true` |
| 站点名单 | `/www/server/free_waf/site.json`（`saiche` / `example.com` / `<SERVER_IP>`，三个都 `"open": true`） |
| 域名映射 | `/www/server/free_waf/domains.json` |
| 注入方式 | nginx `http` 层全局 `access_by_lua_file /www/server/free_waf/waf.lua` |

**全局已开启的规则**（`config.json` 实测）：
```
get        : 403  过滤 uri/参数里的 SQL 注入、XSS
post       : 403  过滤 POST 参数里的 SQL 注入、XSS   ← 我们踩到的就是这条
user-agent : 403  过滤浏览器/蜘蛛/扫描器 UA
cookie     : 403  过滤 Cookie 注入
scan       : 444  拦截常见扫描器
cc         : 444  限速（120 次 / 300 秒）
drop_abroad: 444  禁止境外访问
```

**关键事实**：我们的域名 `gsqc-api.bluearchive-cn.com` 来自手工配置的
`/www/server/panel/vhost/nginx/ba_mitm.conf`，**它不是一个「宝塔站点」**，
所以 `site.json` 里没有它的条目，**面板里按站点关的路子对这条域名不起作用** ——
WAF 对它用的是**全局规则**。

⇒ **结论：只能动「全局」层面的开关。建议只关 `post` 这一条规则，不要关总开关。**

---

## 1. 方案 A（推荐，影响面最小）：只关「POST 过滤」这一条

1. 打开宝塔面板 → 左侧 **软件商店**
2. 切到 **已安装**，找到 **Nginx免费防火墙**（图标是盾牌，作者「民国三年一场雨」）
3. 点它右边的 **设置**
4. 进入后找到「**攻击过滤**／规则开关」区域，里面有：
   `GET` / `POST` / `Cookie` / `User-Agent` / `扫描器` / `CC` / `海外访问`
5. **只把 `POST` 那一项关掉**（其余保持开启）
6. 点 **保存**（插件会自动重载 nginx，约 1–2 秒）

**为什么只关这一条**：我们被拦的是带 `multipart/form-data` 的 POST 请求
（`/api/account/auth`，请求体 1138 字节）。GET 规则的误伤概率低得多，
保持开启对站点更安全。

> 如果面板里 `POST` 这一项找不到独立开关，退到方案 B。

---

## 2. 方案 B（备选）：全局关掉 WAF 总开关

1. 软件商店 → 已安装 → **Nginx免费防火墙** → **设置**
2. 顶部 **总开关** 关掉（显示「未开启／已关闭」）
3. 保存

> 影响面：整机所有站点都不再受该插件保护。
> **仅在方案 A 无效时使用**，用完建议按第 4 节恢复。

---

## 3. 怎么验证已经生效

在**你自己电脑**上（不是服务器上）执行，或者让我在服务器本机跑第一条：

**服务器本机验证（我可以代跑，只读）：**
```sh
curl -skS -D- -o /dev/null -m 8 \
  -X POST -H 'Host: gsqc-api.bluearchive-cn.com' \
  -H 'Content-Type: multipart/form-data; boundary=X' \
  --data-binary '--X
Content-Disposition: form-data; name="protocol"

AHTQLQI65FWJGGGK4KL5AEF57A
--X--' \
  https://127.0.0.1/api/account/auth
```

**判读：**
| 响应 | 含义 |
|---|---|
| `HTTP/2 200` + `content-type: application/json`，body 是 `{"protocol":"Account_Auth",...}` | ✅ WAF 已放行，请求到了我们的桥 |
| `HTTP/1.1 403` + `content-type: text/html`，body 是宝塔错误页（约 1.3 KB，标题「宝塔网站防火墙免费版」） | ❌ 仍被拦，规则未生效 |

**手机侧最终判据**：点「点击任意区域进入游戏」后，`/www/wwwroot/bapatch/logs/api_all_requests.log`
里出现**新的** `POST /api/account/auth` 记录（`mode=bridge`），而不是 403。

---

## 4. 怎么恢复开回来（最重要，别忘）

**恢复方式就是「原路返回」，没有任何不可逆操作：**

- 方案 A 关的 → 回到 **软件商店 → Nginx免费防火墙 → 设置**，把 **`POST`** 那一项重新**打开** → 保存
- 方案 B 关的 → 把 **总开关** 重新**打开** → 保存

开关状态全部写在 `/www/server/free_waf/config.json` 的 `"open"` 字段和
`get/post/cookie/user-agent/scan/cc/drop_abroad` 各子项的 `"open"` 字段里，
**面板开关就是这个文件的可视化，开关一次写一次，不会损坏插件本身**。

**恢复后自查**（面板里应看到）：
- 总开关：已开启
- POST / GET / Cookie / User-Agent / 扫描器 / CC：与你关闭前一致

---

## 5. 如果面板里压根找不到这个插件

说明它可能被卸载了但 nginx 里还留着 include。此时**不要自己去删文件**，
把下面这条命令的输出发给维护者即可（只读）：

```sh
ls -la /www/server/panel/plugin/free_waf/ 2>/dev/null | head -5
grep -rn 'free_waf' /www/server/nginx/conf/nginx.conf 2>/dev/null
```

---

## 6. 一句话总结

> 面板 → 软件商店 → 已安装 → **Nginx免费防火墙** → 设置 → **只关 `POST` 过滤** → 保存。
> 恢复：同一个地方，把 `POST` 重新打开。
> 全程不会破坏插件，也不会影响以后重新开启。
