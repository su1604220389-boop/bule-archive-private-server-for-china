# 蔚蓝档案（国服私服）· 卡密管理后台

纯 Python 标准库 + 原生 JS 的卡密管理平台。直接读写 `sdkcard.py` 的卡密库
`/root/bapatch/cards.json`，**不修改、不重启** `sdkcard.py`；只读解析
`/root/bapatch/sdk.log`。管理端带登录、CSRF、脱敏、审计、登录锁定。

> **红线（本方案严格遵守）**
> - 不修改 `sdkcard.py`、`account_auth_probe.py`、nginx 配置、宝塔配置、证书
> - 不修改宝塔防火墙 / WAF（8899 的放行请在云厂商安全组做）
> - 只新增本目录；不覆盖任何现有文件

---

## 1. 目录结构

```
/www/wwwroot/ba_cardadmin/
  app.py                  主程序：HTTP 服务、登录、API、自检
  db.py                   SQLite 数据层 + cards.json 原子读写 + sdk.log 解析
  templates/index.html    单页界面
  static/app.css          样式（无 CDN）
  static/app.js           前端逻辑（原生 JS，无框架）
  start.sh / stop.sh      nohup 启停
  tools/verify_sdk_compat.py   部署后与 8080 SDK 的兼容性验证
  tests/compat_sdk.py          本地用“sdkcard.py 副本”跑真实协议（不改原文件）
  data/                   运行时自动生成
    admin.db              管理员 / 会话 / 审计 / 卡密元数据 / 登录事件
    cards.json            线上 cards.json 的镜像备份
    backups/              每次写入前的完整备份（自动保留最近 60 份）
    FIRST_LOGIN.txt       首次启动的随机管理员密码（0600）
    access.YYYY-MM-DD.log 访问日志（按天）
    app.YYYY-MM-DD.log    异常日志
    run.log               nohup 标准输出
    app.pid               进程号
```

---

## 2. 与现有服务的关系

| 现有服务 | 关系 |
|---|---|
| `127.0.0.1:8080` `sdkcard.py` | 读写同一个 `cards.json`。它每次请求都重新读文件，所以后台改卡密**立即生效**，无需重启 |
| `/root/bapatch/sdk.log` | 只读解析，绝不写入/移动/截断 |
| `443` nginx / `5000` Shittim / `9097` / `9098` | 完全不接触 |
| 宝塔 / 防火墙 / 证书 | 完全不接触 |

### 为什么不需要改 `sdkcard.py`

`work/ba/bapatch/sdkcard.py` 的 `load_cards()` 每次请求都 `json.load(open(CARDS))`，
`save_cards()` 写回同一结构。本平台写出的 JSON 与它完全同构：

```json
{"cards": {
  "CARD-STRING": {
    "expire": 0,
    "devices": [],
    "bind_one": true
  }
}}
```

- `expire`：unix 秒；`0` = 永不过期
- `devices`：已绑定 DeviceID 数组
- `bind_one`：是否只允许一台设备
- **现有文件里的其它字段/顶层键会原样保留**（本平台只碰这三个字段）

写入方式：**写临时文件 + `fsync` + `os.replace()` 原子替换**，并加
`fcntl.flock` 文件锁。读的时候遇到瞬时半截文件会重试 3 次。
每次写入前把旧内容备份到 `data/backups/`。

> 唯一无法消除的窗口：`sdkcard.py` 自己的 `save_cards()` 是
> `json.dump(d, open(CARDS,'w'))`，不是原子写。如果玩家“首次绑定设备”与本平台
> 写入恰好发生在同一毫秒级窗口，可能丢一次设备绑定。平台侧的读取有重试、写入
> 有锁和原子替换，已经把风险压到最小；建议不要在玩家登录高峰做大批量操作。
> 如真遇到，可从 `data/backups/` 找到操作前文件，把缺失的 `devices` 手工补回。

---

## 3. 部署

> 以下命令在服务器上执行（路径按实际调整）。需要用 root，或者确保对
> `/root/bapatch/cards.json` 有读写权限。

```bash
# 1) 上传整个 ba_cardadmin 目录到 /www/wwwroot/
cd /www/wwwroot
tar -xzf ba_cardadmin.tar.gz          # 或 scp -r
cd /www/wwwroot/ba_cardadmin
chmod +x start.sh stop.sh

# 2) 部署前体检（只读，不写 cards.json）
python3 app.py --check

# 3) 启动（默认 0.0.0.0:8899）
./start.sh

# 4) 拿首次登录密码
cat data/FIRST_LOGIN.txt
```

`start.sh` 会：

- 先检查 `data/app.pid` 防止重复启动
- 用 `ss -lntp` + 实际 connect 双重检查 8899 是否被占用
- `nohup python3 app.py --port 8899` 后台启动
- 轮询 `/healthz`（最多约 30 秒，首次可能要先解析较大的 sdk.log），
  启动失败会打印 `data/run.log` 最后 30 行

常用写法：

```bash
PORT=8898 ./start.sh            # 换端口
HOST=127.0.0.1 ./start.sh       # 只监听本机（配合 SSH 隧道）
DATA_DIR=/www/wwwroot/ba_cardadmin/data \
CARDS=/root/bapatch/cards.json \
SDK_LOG=/root/bapatch/sdk.log ./start.sh
```

停止：

```bash
./stop.sh
```

### 端口检查

8899 不在已知服务列表中（443 / 5000 / 8080 / 9097 / 9098），**大概率空闲**。
但部署机是否已被别的程序占用只能现场确认：

```bash
ss -lntp | grep ':8899' || echo '8899 空闲'
```

如果被占用，`start.sh` 会拒绝启动并提示。换端口：

```bash
PORT=8898 ./start.sh
```

然后访问 `http://服务器IP:8898`。

---

## 4. 首次登录 / 密码机制

- 第一次启动时，如果 SQLite 里没有任何管理员，自动创建：
  - 用户名 `admin`
  - 密码 **18 位随机**（`secrets` 生成，不在代码里硬编码）
  - PBKDF2-HMAC-SHA256（260000 次）+ 16 字节随机 salt，存 SQLite
  - 明文只出现在两处：启动 stdout（`data/run.log`，0600）与
    `data/FIRST_LOGIN.txt`（0600）
- 登录后请点右上角「改密码」。修改密码会注销其它设备的会话。
- 忘记密码：

```bash
python3 app.py --reset-admin-password
# 或指定管理员
python3 app.py --reset-admin-password --admin-user admin
```

新密码会打印到 stdout，并写入 `data/ADMIN_RESET.txt`（0600）。

- 会话：随机 32 字节 token（`secrets.token_urlsafe(32)`），Cookie
  `ba_admin_session` 为 HttpOnly + SameSite=Strict，默认 12 小时。
  SQLite 里只存 token 的 sha256，不存明文 token。
- 登录失败：同一用户名 + IP 5 次失败锁 10 分钟；同一用户名全局 20 次、
  同一 IP 全局 20 次也会锁。锁定期返回 429 + `Retry-After`。

---

## 5. 功能

- **仪表盘**：总卡密 / 可用 / 已过期 / 已绑定 / 今日新增 / 今日登录，
  最近 20 条登录，以及 `cards.json`、`sdk.log`、解析偏移等系统状态。
- **卡密管理**
  - 分页（20/50/100/200）、模糊搜索、按 可用/已过期/未绑定/已绑定/永不过期 筛选
  - 新建单个：自动生成（长度/字符集/前缀可配）或自定义字符串
  - 批量生成：一次 1–5000 个，生成完可直接复制/下载 TXT
  - 批量操作：删除、延期 N 天、设为永不过期、解绑设备
  - 单个：改过期时间、解绑、复制、显示明文、删除
  - 导入：粘贴文本，一行一个，自动去重/跳过已存在/拒绝非法字符
  - 导出：TXT / CSV，可按当前筛选、全部或勾选项，可只导出未绑定设备的
  - 默认脱敏显示（`abcd****wxyz`），点击「显示」才返回明文并写审计
- **登录日志**：从 `sdk.log` 解析 成功 / 卡密不正确 / 已过期 / 设备超限，
  显示时间、脱敏卡密、DeviceID、来源（卡密登录/快速登录）
- **审计日志**：登录、退出、改密、新建、生成、导入、导出、显示明文、
  修改、删除、延期、解绑，记录 谁/何时/IP/动作/对象/影响条数/详情

---

## 6. 登录日志解析（只读）

`sdkcard.py` 的日志格式：

```
10:41:17 /user/login dev=09a4d0ab0ee93616
BODY {"OpenID":"11111111111",...}
LOGIN OK 11111111111 dev=09a4d0ab0ee93616
10:42:08 /user/quick-login dev=09a4d0ab0ee93616
BODY {}
QUICK OK 11111111111 dev=09a4d0ab0ee93616
```

注意点（实现里都处理了）：

- 日志行只有 `HH:MM:SS`，没有日期。平台以文件 mtime 为最后一条时间戳的锚点，
  反向推断跨零点的日期（时间倒退超过 12 小时才判定跨天，避免多线程日志乱序误判）。
- `sdkcard.py` 对“卡密已过期 / 设备超限”**直接 return，不写日志**，只在请求
  开头留下 `BODY {"OpenID":...}`。平台会把这种没有结果行的请求按当前卡密状态
  推断为「已过期」或「设备超限」；推断不出来的标为「已拒绝（未记录原因）」。
  这是 sdkcard 的日志缺口，不是平台漏读。
- 增量读取：记录 inode + 字节偏移；文件被 `sdk.log` 截断/轮转会重置偏移并
  增加代次，避免旧偏移上的新内容被误判重复。
- 首次启动最多回读最近 10 MB（`--initial-log-bytes`），更早的历史不导入。
- 事件默认保留 180 天（`--event-retention-days`）。

---

## 7. 安全清单

- 所有 `/api/*`（除 `/api/login`）未登录返回 401；未知 `/api/*` 也先校验会话。
- 所有写接口：CSRF token（`X-CSRF-Token`，随会话下发）+ Origin/Referer 校验
  + `Content-Type: application/json`。
- SQL 全部参数化；没有字符串拼接用户输入。
- 请求体上限 2 MB；静态文件白名单扩展名 + `realpath` 防路径穿越。
- 卡密默认脱敏；显示明文、复制、导出都会写审计。
- 密码 PBKDF2-HMAC-SHA256 + 随机 salt；会话只存 hash；Cookie HttpOnly/SameSite。
- CSP、`X-Frame-Options: DENY`、`nosniff`、`no-referrer`。
- 审计日志不保存密码；明文卡密只在需要显示/导出时出现。

### 公网暴露建议

1. **云厂商安全组只放行你自己的出口 IP 到 8899/TCP**，不要 `0.0.0.0/0`。
2. 这是 HTTP 明文面板，密码在公网传输不加密。更稳的做法：
   ```bash
   # 服务器只监听本机
   HOST=127.0.0.1 ./start.sh
   # 本地电脑建立隧道后访问 http://127.0.0.1:8899
   ssh -L 8899:127.0.0.1:8899 root@服务器IP
   ```
3. 不要在宝塔里为此改现有防火墙/WAF；端口放行在云控制台做。
4. 如需 HTTPS，请新建独立站点/反代或使用 Cloudflare Tunnel；**不要改现有
   443 的 stream SNI 配置**。反代时若需要真实 IP，再加 `--trust-proxy`。

---

## 8. 自检与兼容性验证

### 8.1 全量自检（不碰线上）

```bash
python3 app.py --selftest
```

在临时目录里跑**真实 HTTP 服务 + 真实 cards.json 读写**，覆盖：建库、建管理员、
登录/CSRF/401、新建、批量生成 100、列表脱敏、显示明文、改期、解绑、批量延期、
导出 TXT/CSV、导入、删除、仪表盘、sdk.log 解析（含跨零点/过期/设备超限推断/
截断后续读）、路径穿越、2MB 限制、并发原子写、sdkcard 数据结构兼容、登录锁定、
退出、镜像/备份/访问日志。

本机实际结果：**60 项全部通过**。

### 8.2 本地真实 sdkcard 协议验证

```bash
python tests/compat_sdk.py
```

它把 `work/ba/bapatch/sdkcard.py` **复制**到临时目录，仅替换副本里的 4 个路径
常量和监听端口，然后启动真实 `/user/login`，验证：

- 平台新建的卡密 → SDK 返回 `Code: 200`
- sdkcard 写回 `devices` → 平台能读到
- `bind_one` 第二台设备 → 拒绝
- 过期卡 / 未知卡 → 拒绝
- sdkcard 重写文件后平台继续写入，设备绑定不丢
- 原始 `sdkcard.py` 的 sha256 不变

本机实际结果：**11 项全部通过**。

### 8.3 部署后验证真实 8080（关键）

```bash
cd /www/wwwroot/ba_cardadmin
python3 tools/verify_sdk_compat.py --password-file data/FIRST_LOGIN.txt
# 如果已经改过密码，用当前密码：
python3 tools/verify_sdk_compat.py --password '当前管理员密码'
```

它会：登录后台 → 新建一张 `COMPAT-PLATFORM-...` 临时卡 → 用真实
`127.0.0.1:8080/user/login` 登录 → 校验 `Code=200` 和设备绑定 → 删除临时卡。

> 这是唯一会写线上 `cards.json` 的验证脚本，只新增 1 张临时卡并删除。

### 8.4 curl 冒烟

```bash
curl -s http://127.0.0.1:8899/healthz
curl -s -c /tmp/ck.txt -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"FIRST_LOGIN里的密码"}' \
  http://127.0.0.1:8899/api/login
curl -s -b /tmp/ck.txt http://127.0.0.1:8899/api/dashboard
curl -s -b /tmp/ck.txt 'http://127.0.0.1:8899/api/cards?q=&size=20'
```

写接口需要登录响应里的 `csrf`：

```bash
curl -s -b /tmp/ck.txt -H 'Content-Type: application/json' \
  -H 'X-CSRF-Token: <csrf>' \
  -d '{"count":3,"length":20,"prefix":"TEST-"}' \
  http://127.0.0.1:8899/api/cards/generate
```

---

## 9. 日常运维

### 启动 / 停止 / 重启

```bash
./stop.sh && ./start.sh
```

### 日志

```bash
tail -f data/run.log
tail -f data/access.$(date +%F).log
tail -f data/app.$(date +%F).log
```

访问日志**按天分文件**：`data/access.YYYY-MM-DD.log`。

### 备份

- 每次写 `cards.json` 前自动备份到 `data/backups/cards-*.json`（保留最近 60 份）
- `data/cards.json` 是线上文件的镜像
- 建议额外定时备份整个 `data/` 与 `/root/bapatch/cards.json`

### 恢复

```bash
./stop.sh
# 1) 先确认备份是合法 JSON
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(len(d["cards"]))' \
  data/backups/cards-YYYYmmdd-HHMMSS-xxxx.json
# 2) 复制回线上（保留原文件权限/属主）
cp -a /root/bapatch/cards.json /root/bapatch/cards.json.bak.$(date +%s)
cp data/backups/cards-YYYYmmdd-HHMMSS-xxxx.json /root/bapatch/cards.json
python3 app.py --check
./start.sh
```

### 升级代码

```bash
./stop.sh
# 只覆盖 app.py / db.py / templates / static / tools / tests，保留 data/
python3 app.py --check
./start.sh
```

**不要删除 `data/`**（里面有管理员、审计、备份）。`cards.json` 始终在
`/root/bapatch/`，升级不会动它。

### 修改会话时长 / 数据保留

```bash
PORT=8899 nohup python3 app.py --session-hours 24 --event-retention-days 365 \
  >> data/run.log 2>&1 &
```

或把这些参数写进 `start.sh`。

### 首次管理员密码文件丢了

```bash
python3 app.py --reset-admin-password
```

---

## 10. 开机自启（可选）

> 任务要求用 `nohup`，不强制 systemd。以下任选其一，不要动现有服务。

**A. `/etc/rc.local`（简单）**

```bash
# 文件末尾、exit 0 之前
/www/wwwroot/ba_cardadmin/start.sh
```

**B. 宝塔「计划任务」**

新建 Shell 脚本任务，执行周期选“每分钟”并加锁，或直接用宝塔的“开机启动”
能力执行 `/www/wwwroot/ba_cardadmin/start.sh`。

**C. systemd（有 root 且愿意用）**

```ini
# /etc/systemd/system/ba-cardadmin.service
[Unit]
Description=BA Card Admin
After=network.target

[Service]
Type=simple
WorkingDirectory=/www/wwwroot/ba_cardadmin
ExecStart=/usr/bin/python3 app.py --port 8899
Restart=on-failure
UMask=0077

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload && systemctl enable --now ba-cardadmin
```

用了 systemd 就不要再执行 `start.sh`，避免两个进程抢 8899。

---

## 11. API 一览

除 `/api/login` 外都需要会话 Cookie；写接口还需要 `X-CSRF-Token`。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/login` | `{username,password}`，下发 HttpOnly Cookie + csrf |
| POST | `/api/logout` | 注销当前会话 |
| POST | `/api/password` | `{old_password,new_password}` |
| GET | `/api/me` | 当前管理员、csrf、配置 |
| GET | `/healthz` | 健康检查（不需要登录） |
| GET | `/api/dashboard` | 统计 + 最近 20 条登录 + 系统状态 |
| GET | `/api/cards?page=&size=&q=&status=&sort=` | 卡密列表（脱敏） |
| POST | `/api/cards/create` | `{card?/length/prefix/charset, expire_days, bind_one, note}` |
| POST | `/api/cards/generate` | `{count,length,prefix,charset,expire_days,bind_one}` |
| POST | `/api/cards/import` | `{text,expire_days,bind_one}` |
| POST | `/api/cards/export` | `{format:txt/csv, scope:all/filter/ids, q,status,ids,only_unused}` |
| POST | `/api/cards/reveal` | `{card_id}` 返回明文并记审计 |
| POST | `/api/cards/update` | `{card_id,never/expire_at/expire_days,bind_one,note}` |
| POST | `/api/cards/bulk` | `{action:delete/extend/never/unbind/bind_one, ids或scope,q,status,days}` |
| GET | `/api/logs?page=&size=&q=&result=` | 登录日志 |
| GET | `/api/audit?page=&size=&q=` | 审计日志 |

---

## 12. 故障排查

| 现象 | 处理 |
|---|---|
| `start.sh` 提示端口被占用 | `ss -lntp \| grep ':8899'`，换 `PORT=8898 ./start.sh`，或停掉占用进程 |
| 访问 8899 超时 | 云厂商安全组是否放行；`curl http://127.0.0.1:8899/healthz` 本机是否通 |
| 登录 401 | 密码错；看 `data/FIRST_LOGIN.txt` 或重置密码 |
| 登录 429 | 触发 5 次失败锁定，等 10 分钟 |
| 页面 403 CSRF | 刷新页面重新取 csrf；确认反向代理没有改写 Origin/Host |
| 仪表盘报 `cards.json 解析失败` | 文件损坏。服务已停止写入；从 `data/backups/` 恢复 |
| sdk.log 没数据 | 路径不对、权限不足，或 sdkcard 还没产生登录；`--check` 会提示 |
| 卡密显示「已拒绝（未记录原因）」 | sdkcard 对过期/设备超限不写日志，平台只能推断 |
| 卡密封面显示 `—` | 平台接管前就存在的卡，没有真实创建时间（不伪造） |
| 修改后 SDK 端没生效 | 确认 `--cards` 指向 `/root/bapatch/cards.json`；`sdkcard.py` 每次请求都会重读 |

---

## 13. 已知边界

- 单实例部署：不要同时起两个后台指向同一个 `cards.json`（虽然写锁能串行，
  但元数据/会话会分叉）。
- 不内置 HTTPS；公网请限制来源 IP，或用 SSH 隧道。
- 首次部署时，存量卡密的“创建时间”显示 `—`；今日新增只统计平台接管后创建的卡。
- 登录日志里“已过期/设备超限”是按当前卡密状态推断的，因为 sdkcard 不记录这两种拒绝。
- `sdkcard.py` 自己写 `cards.json` 不是原子的；平台读取有重试，但仍存在理论上的
  毫秒级竞态（见第 2 节）。
- 平台不读取游戏桥 `account_auth_probe.py` 的日志；登录情况只来自 `sdk.log`。
- 首次导入 `sdk.log` 默认只回读最后 10 MB。

---

## 14. 本机自检记录（交付时）

```
python3 app.py --selftest
自检全部通过：60 项

python tests/compat_sdk.py
兼容性验证全部通过：11 项
  - sdkcard /user/login 接受平台新建的卡密（Code 200）
  - sdkcard 写回的 devices 被平台读到
  - bind_one：第二台设备被拒绝
  - 过期卡 / 未知卡被拒绝
  - 原始 sdkcard.py 未被修改（sha256 不变）
```

真实 8080 的验证请在部署后执行 `tools/verify_sdk_compat.py`（见 8.3）。
