# 服务器宕机排查 + 服务重启（OOM 事件，2026-11-20）

- 时间：2026-11-20 01:35–01:41（Asia/Shanghai）｜ 执行：srv-ops
- 范围限定：**只做只读排查 + 重启服务**；未改任何代码/配置、未部署、未删文件、未动 swap/systemd 限制

## 一句话结论

**服务已全恢复**——机器在 **00:46:28 已经整机重启过一次**（当前 uptime 54 min），
systemd 托管的服务（ba-shittim / ba-sdk / nginx / php-fpm-82 / mysqld / redis）**都随开机自动起来了**，
**唯一没起来的是手工 setsid 启动的桥（9097）**，我用原样命令把它拉起（pid 5527，`curl http://127.0.0.1:9097/` → **200**）。

**OOM 真凶：无法定论（没有证据）。** 见 §2。

---

## 1. 现状（只读采集）

### 1.1 系统
```
free -h（重启桥之前）:
               total        used        free      shared  buff/cache   available
Mem:           1.6Gi       753Mi        62Mi        83Mi       792Mi       609Mi
Swap:          1.0Gi          0B       1.0Gi

uptime: 01:35:44 up 49 min, 1 user, load average: 0.09, 0.06, 0.06
df -h /: /dev/vda3  40G  25G  13G  66%  /
```

### 1.2 服务状态（采集时刻）
| 服务 | 状态 | 说明 |
|---|---|---|
| ba-shittim | **active** | 自 00:47:02 起（开机自动），Main PID 2439 (tmux) / 子进程 2440 (dotnet) |
| ba-sdk | **active** | 8080 在听（pid 752） |
| php-fpm-82 | **active** | 自 00:46:42 起 |
| nginx | **active** | 自 00:46:43 起，80/443/8081 在听 |
| mysqld | **active** | 服务名是 `mysqld.service`（不是 mysql/mariadb），3306 在听（pid 2096） |
| redis | **active** | |
| **桥 account_auth_probe（9097）** | **未运行** | 无 systemd 单元，手工 setsid 启动；重启后没人拉起它 |

### 1.3 端口（重启桥之前）
```
443 / 80 / 8081  -> nginx (pid 1296/1297/1298)
5000 / 5100      -> dotnet (pid 2440)
8080             -> python3 sdkcard.py (pid 752)
9097             -> **无** ← 唯一缺的
3306             -> mysqld (pid 2096)
```

### 1.4 内存 Top（采集时刻）
```
root  2440  dotnet  /www/wwwroot/ba_srv/Shittim-Server.dll    RSS 201,444 KB (12.2%)
mysql 2096  mysqld --basedir=/www/server/mysql                RSS 187,612 KB (11.3%)
root  2474  /opt/mslx/MSLX-Daemon                             RSS  77,472 KB (4.7%)
root  4443  BT-Panel                                          RSS  45,900 KB (2.7%)
www   1297/1298 nginx worker                                  RSS  42,200/41,660 KB (2.5% each)
```

---

## 2. OOM 证据（**关键：没有找到**）

### 2.1 直接证据全部为空
```
journalctl -b -1 | grep -iE 'out of memory|oom-kill|killed process|memory cgroup'  →  **0 条**
journalctl -b 0  | grep -icE 'oom|out of memory|killed process'                    →  1（本次 boot，见下）
/var/log/messages  命中 = 0   ｜ /var/log/syslog 命中 = 0  ｜ /var/log/kern.log 命中 = 0
grep -c 'Kernel panic' /var/log/messages → 0
```
> 本次 boot 的那 1 条命中是 `journalctl` 自身启动参数里含 "oom" 字样的无关行，不是内核 OOM 记录。

### 2.2 时间线（这才是真的异常点）
```
上个 boot 最后一条 journal 记录 : 2026-11-20T00:06:43  （UFW BLOCK，正常流量日志）
本次 boot 内核启动              : 2026-11-20T00:46:28
                                   ↑ 中间 **39 分 45 秒 完全没有日志**
uptime -s                       : 2026-11-20 00:46:28
```
**⇒ 机器在 00:06:43 之后「日志突然断掉、直到 00:46:28 重新开机」**，中间近 40 分钟无任何内核/服务记录。

### 2.3 结论（严谨表述）
- **没有**任何 OOM Killer 的痕迹（无 `invoked oom-killer`、无 `Killed process`、无 memory cgroup 记录），
  `/var/log/messages|syslog|kern.log` 里也一条都没有。
- 现象更像**整机层面被强制中断**（控制台/宿主侧重启或硬复位），而不是 Linux 内部 OOM 杀进程——
  否则 journal 一定会留下 `kernel: Out of memory: Killed process ...` 这类行（本机 journal 是持久化的，上一 boot 可读）。
- **因此「谁是真凶」无法从日志判定**：`dmesg` 权限也受限（`kernel.dmesg_restrict=1`），且当前 dmesg 只有本次 boot 的 875 行。
- 唯一能确定的候选压力源（重启后仍在跑的内存大户）：
  `dotnet Shittim-Server` RSS ≈ **190–200 MB**、`mysqld` RSS ≈ **187 MB**，
  两者合计约占 1.6 GB 物理内存的 **24%**；其余为宝塔面板/阿里云监控/mslx 等常驻组件。

---

## 3. 重启动作（只做了 1 个）

### 3.1 桥（9097）—— 唯一需要动手的服务
按**原样启动方式**（没有自己发明）：
```bash
( umask 007; cd /www/wwwroot/bapatch/tools && setsid nohup python3 account_auth_probe.py \
    >> /www/wwwroot/bapatch/logs/bridge_stdout.log 2>&1 & )
```
启动结果：
```
9097_UP after 2s
实例数 = 1
5527 python3 account_auth_probe.py
cwd = /www/wwwroot/bapatch/tools        ← 确认在正确工作目录（不用相对路径开关会读不到）
curl http://127.0.0.1:9097/  ->  200
```
> 桥没有 systemd 单元（`systemctl list-units | grep bridge` 无结果），这也解释了为什么整机重启后它不会自动起来。

### 3.2 其它服务 —— **没有重启**
ba-shittim / ba-sdk / nginx / php-fpm-82 / mysqld / redis 全部已在运行、端口在听、HTTP 正常，
按「不要无差别全重启」的要求，全部**保持原样未动**。

---

## 4. 重启后验证

```
端口：
  443/80/8081 -> nginx ｜ 5000/5100 -> dotnet(2440) ｜ 8080 -> sdkcard(752)
  **9097 -> python3(5527)** ｜ 3306 -> mysqld(2096)

HTTP：
  http://127.0.0.1:9097/            -> **200**   （桥，恢复）
  http://127.0.0.1:5000/            -> 404       （Shittim 无根路由，属正常）
  http://127.0.0.1:8081/            -> **302**   （面板跳登录，正常）
  http://127.0.0.1:8080/            -> **200**   （SDK）
  https://127.0.0.1/api/health (Host=example.com) -> **200**
  https://127.0.0.1/api/state  (Host=example.com) -> **200**
  http://127.0.0.1:8081/pages/gacha_rates.php          -> **302**

服务：
  ba-shittim active ｜ ba-sdk active ｜ php-fpm-82 active ｜ nginx active ｜ mysqld active ｜ redis active
  桥实例数 = 1
```

## 5. 内存复查

```
               total        used        free      shared  buff/cache   available
Mem:           1.6Gi       832Mi        77Mi        83Mi       698Mi       **529Mi**
Swap:          1.0Gi          0B       1.0Gi
```
**available = 529 MB > 300 MB 阈值** ⇒ 按你的规则不需要额外上报 Top5；但为完整起见给出当前 Top：
```
root  2440  dotnet Shittim-Server      RSS 194,572 KB (11.8%)
mysql 2096  mysqld                     RSS 187,532 KB (11.3%)
root  2474  MSLX-Daemon                RSS  78,048 KB (4.7%)
root  5757  BT push_msg.py             RSS  68,308 KB (4.1%)（瞬时）
root  4443  BT-Panel                   RSS  45,900 KB (2.7%)
```

---

## 6. 红线遵守情况

- ✅ 未改任何代码、配置；未部署；未删文件
- ✅ 未清理缓存、未动 swap 配置、未动 systemd 限制
- ✅ 桥按原样命令启动（含 `cd /www/wwwroot/bapatch/tools` + `umask 007`）
- ✅ 只动了桥（重启），其它服务因已正常而未重启
- ⚠ `dmesg` 受 `kernel.dmesg_restrict=1` 限制，且当前 dmesg 只含本次 boot；这是「拿不到 OOM 真凶」的客观原因

## 7. 建议（不在本次执行范围）

1. **给桥做 systemd 单元**（或开机脚本），否则每次整机重启都要人工拉起（这次就漏了）。
2. 若再发生类似「日志断档 → 整机重启」，可查云厂商控制台的重启/迁移事件（本机日志无法区分）。
3. 内存余量约 529 MB / 1.6 GB，`dotnet + mysqld` 已占 ~380 MB；后续若要加服务需留意。
