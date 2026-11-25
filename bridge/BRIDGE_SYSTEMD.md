# 桥（账户鉴权桥）systemd 单元化：ba-bridge.service

- 时间：2026-11-20 01:44（Asia/Shanghai）｜ 执行：srv-ops
- 范围：**只新增了一个 systemd 单元** `/etc/systemd/system/ba-bridge.service`
- **未改桥脚本一个字、未改任何配置文件、未重启整机**
- **最终判定：建好并切换成功 · 开机自启已启用 · 崩溃自动拉起实测通过 · KEEP**

## 一句话结论

桥已从「手工 `setsid nohup`」迁到 systemd：`ba-bridge.service` = **active (running) + enabled**，
`/proc/<pid>/cwd` = **`/www/wwwroot/bapatch/tools`**（WorkingDirectory 生效），
`kill -9` 后 **6 秒自动拉起**（`NRestarts` 0→1），桥脚本 md5 保持 `891178d6…` 未变。

---

## 1. 前置确认（只读）

```
systemd 版本 : systemd 249 (249.11-0ubuntu3.23)     ⇒ 支持 StandardOutput=append:
python3      : /usr/bin/python3  (Python 3.10.12)
现有桥实例   : pid 5527 ｜ user root ｜ cwd /www/wwwroot/bapatch/tools ｜ 实例数 1
环境变量     : 只有系统默认（PATH/LANG/HOME/SSH_* 等），**无 BA_/_BA/CN_/PYTHON* 自定义变量** ⇒ 单元里不需要 Environment=
日志         : /www/wwwroot/bapatch/logs/bridge_stdout.log（174,532 B，可写）
同名单元     : /etc/systemd/system/ba-bridge.service **原本不存在**
```
> 说明：`/www/wwwroot/bapatch/tools/logs/` 不存在；历史日志一直写在 `/www/wwwroot/bapatch/logs/bridge_stdout.log`（绝对路径）。

## 2. 单元文件全文

```ini
[Unit]
Description=BA auth bridge (account_auth_probe) on 9097
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/www/wwwroot/bapatch/tools
UMask=007
ExecStart=/usr/bin/python3 /www/wwwroot/bapatch/tools/account_auth_probe.py
Restart=always
RestartSec=5
StandardOutput=append:/www/wwwroot/bapatch/logs/bridge_stdout.log
StandardError=append:/www/wwwroot/bapatch/logs/bridge_stdout.log

[Install]
WantedBy=multi-user.target
```
`systemd-analyze verify` 结果（只有一条与本次无关的 snapd 警告）：
```
/lib/systemd/system/snapd.service:23: Unknown key name 'RestartMode' in section 'Service', ignoring.
```

## 3. 切换过程（前后对比）

### 切换前（手工实例）
```
ps: 5527  5525  python3 account_auth_probe.py      （cwd=/www/wwwroot/bapatch/tools，user=root）
ss: LISTEN 127.0.0.1:9097  users:(("python3",pid=5527,fd=3))
```
停旧实例：`kill 5527`（**未用 -9**）→ 进程正常退出 → 9097 释放（1 次检查即释放）。

### 切换后（systemd 托管）
```
systemctl daemon-reload && systemctl enable --now ba-bridge
Created symlink /etc/systemd/system/multi-user.target.wants/ba-bridge.service → /etc/systemd/system/ba-bridge.service
**9097_UP after 2s**
ps: 6364  /usr/bin/python3 /www/wwwroot/bapatch/tools/account_auth_probe.py
ss: LISTEN 127.0.0.1:9097  users:(("python3",pid=6364,fd=3))
```

## 4. 九项验证（实际输出）

### ① `systemctl status` → active (running) + enabled
```
● ba-bridge.service - BA auth bridge (account_auth_probe) on 9097
     Loaded: loaded (/etc/systemd/system/ba-bridge.service; **enabled**; vendor preset: enabled)
     Active: **active (running)** since Fri 2026-11-20 01:44:19 CST
   Main PID: 6364 (python3)
      Tasks: 1 (limit: 1830)
     Memory: 22.2M
        CPU: 154ms
     CGroup: /system.slice/ba-bridge.service
             └─6364 /usr/bin/python3 /www/wwwroot/bapatch/tools/account_auth_probe.py
  is-active  = active
  is-enabled = enabled
```

### ② `ss -lntp | grep :9097` → 只有一个进程
```
LISTEN 0  5  127.0.0.1:9097  0.0.0.0:*  users:(("python3",pid=6364,fd=3))
```

### ③ 进程数 = 1
```
6364 /usr/bin/python3 /www/wwwroot/bapatch/tools/account_auth_probe.py
实例数 = 1
```

### ④ `/proc/<pid>/cwd` → **`/www/wwwroot/bapatch/tools`**（最关键）
```
pid = 6364
cwd = /www/wwwroot/bapatch/tools       ← WorkingDirectory 生效 ✅
exe = /usr/bin/python3.10
user = root ｜ rss = 32,492 KB
```
**用相对路径读开关文件佐证**（通过 `/proc/<pid>/cwd/` 访问）：
```
cn_4000.txt   存在，内容 = [0]
cn_1005.txt   存在，内容 = [1]
cn_26000.txt  存在，内容 = [1]
```
> 注：`cn_wrap_mode.txt` / `cn_devid.txt` 本来就在 `/www/wwwroot/bapatch/`（不是 tools/），桥靠"脚本目录 → 兜底目录"顺序找，
> 所以它们在 cwd 里找不到是**预期**，不影响运行；tools 下的三个开关都能读到，证明 cwd 正确。

### ⑤ `curl http://127.0.0.1:9097/` → 非 5xx
```
HTTP 200
```

### ⑥ 真实链路（Auth 1002 + LoginSync 1019）
```
ensure_session → account_id = 4
Account_Auth(1002): HTTP 200 ｜ 418,741 B ｜ ErrorCode=None
LoginSync(1019)   : HTTP 200 ｜ 771,613 B ｜ ShopRecruits = 529 条
```
（LoginSync 771 KB，与 systemd 化之前经桥的 777–783 KB 同量级；ShopRecruits 仍 529 条。）

### ⑦ 自动拉起测试（对真实 pid `kill -9`）
```
当前 pid = 6364 ｜ NRestarts = 0
kill -9 6364
**6s 后已自动拉起：旧 pid=6364 → 新 pid=6699**
systemctl is-active = active ｜ NRestarts = **1**
实例数 = 1
LISTEN 127.0.0.1:9097  users:(("python3",pid=6699,fd=3))
```
journal 证据：
```
01:44:42 ba-bridge.service: Main process exited, code=killed, status=9/KILL
01:44:42 ba-bridge.service: Failed with result 'signal'.
01:44:47 ba-bridge.service: Scheduled restart job, restart counter is at 1.
01:44:47 ba-bridge.service: Started BA auth bridge (account_auth_probe) on 9097.
```

### ⑧ 开机自启（`is-enabled`，未重启机器）
```
enabled
```
（`WantedBy=multi-user.target` 的软链已创建：`/etc/systemd/system/multi-user.target.wants/ba-bridge.service`）

### ⑨ 日志尾部（无新异常）
```
[warn] inner len 240 != 432
[warn] inner len 240 != 432
…（仍是历史就有的 [warn] inner len 提示，属既有格式告警，非本次引入）
```
journal 里除上面 kill -9 测试的 4 行外，无任何 error/warn 级记录。

## 5. 未动项复核

```
/www/wwwroot/bapatch/tools/account_auth_probe.py
  md5    = 891178d6ba9647d27a1d8b2f5d7c2d64   ← 与切换前完全一致（未改一个字）
  sha256 = 15758f0ea007dcfba4e46fc4620dd183329381c194f00878abd6acc21cd2ee01
/www/wwwroot/ba_srv/Shittim-Server.dll
  sha256 = c013f4427ad01d44c00cc43af3de817b800638fcd8ec0ee55de41126aed106aa（未动）
ba-shittim / nginx / php-fpm-82 均 active（未重启）
```

## 6. 回滚

```
备份目录：/root/BRIDGESVC_20261120_014417/
   ORIGINAL_START.txt   （原始 ps 原文 + 历史启动命令 + 进程信息）
   ROLLBACK.sh          （停用并删除单元 → daemon-reload → 用原命令行手工拉起 → 轮询 9097 → curl）
```

**ROLLBACK.sh 完整路径：**
```
/root/BRIDGESVC_20261120_014417/ROLLBACK.sh
```
其核心命令（与原启动方式完全一致）：
```bash
systemctl disable --now ba-bridge && rm -f /etc/systemd/system/ba-bridge.service && systemctl daemon-reload
( umask 007; cd /www/wwwroot/bapatch/tools && setsid nohup python3 account_auth_probe.py \
    >> /www/wwwroot/bapatch/logs/bridge_stdout.log 2>&1 & )
```

## 7. 备注 / 后续

- 以后**不需要**再手工 `cd tools && setsid nohup …`；直接 `systemctl restart ba-bridge` 即可（单元已保证 cwd）。
- 桥崩溃/被 OOM 杀掉会自动重启（`Restart=always`，5 秒后），`systemctl restart ba-bridge` 次数可用 `systemctl show ba-bridge -p NRestarts` 观察。
- 今天整机重启漏起 9097 的问题，已由 `enabled` + `WantedBy=multi-user.target` 解决（下次开机自动起）。
- 日志仍写 `/www/wwwroot/bapatch/logs/bridge_stdout.log`（systemd `append:` 方式，不需要管道/重定向）。
