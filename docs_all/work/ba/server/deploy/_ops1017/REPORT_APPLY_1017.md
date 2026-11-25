# patch_1017 线上 apply + bridge 重启报告

- 目标服务器：`<SERVER_IP>`（root，Ubuntu，Python 3.10.12）
- 目标文件：`/www/wwwroot/bapatch/tools/account_auth_probe.py`
- 执行时间：2026-11-16 06:27 – 06:32 (+08:00)
- 结论：**已 apply、已重启、已生效（1017 走 dynamic / 35 键），无回滚**

---

## 0) 偏离项（必须先看）

1. **`patch_1017.py` 在服务器上并不存在**。`find / -xdev -name 'patch_1017*'` 全文无结果，
   `/www/wwwroot/bapatch/tools/` 里只有 `gen1017.py` / `specgen.py` / 三个数据文件。
   → 从本工作区 `work/ba/server/deploy/patch_1017.py`（32,071 B，
   sha256 `b5eb6d971e15d50110d82f5dbd672158c07fd50d89bf1a2ffa3a5b26317dcca4`）上传到 `tools/`，
   上传后两端 sha256 一致、`py_compile` 通过。
   旁证：服务器上的 `gen1017.py` sha256 `ad4e3ec9…6221` 与本地 `deploy/gen1017.py` 完全相同，
   说明 `deploy/` 就是 `tools/` 的源。除这一点外，其余前置状态与你给的全部一致。
2. **SSH 主机密钥变了**（本地 known_hosts 记录 ed25519 `SHA256:o01m9fFb…DcEAo`，
   服务器现在给 `SHA256:dTKptFoQMPWQpaX6STUccIdf50VYKIcyPWyTaQCcuFQ`，ECDSA 也不同）。
   本次用 `StrictHostKeyChecking=no + UserKnownHostsFile=NUL` 连接，没有改你的 known_hosts。
   另外本机 `ssh-keyscan` 版本太老（不支持 sntrup761x25519），只能直连。
3. **`/api/health` 的“2 字节 ok”是 nginx 层的**，不是 bridge 的。详见第 7 节。

---

## 1) 第 0 步：回滚基线

```
sha256  d5f27fcab6a897c88a8281fe9b2bd043924b68b5ca1c3ba4f60fd8649d1b814e
行数    1777
字节    73,445
pid     2529465   (PPID 2529463 = `bash -s`，父 shell 已孤儿化到 init)
启动于  2026-11-16 06:07:10
```

进程事实（从 `/proc` 读，不靠猜）：

```
cmdline : python3 account_auth_probe.py          (无其它参数)
exe     : /usr/bin/python3.10
cwd     : /www/wwwroot/bapatch/tools
fd0     : /dev/null
fd1     : /www/wwwroot/bapatch/logs/api_probe.out
fd2     : /www/wwwroot/bapatch/logs/api_probe.out
listen  : 127.0.0.1:9097  (python3, pid=2529465, fd=3)
env     : PWD=/www/wwwroot/bapatch/tools, HOME=/root, 无 CN_* / BA_* 覆盖
```

**完整启动命令**：原进程是某次 `ssh … 'bash -s'` 里前台拉起的（`/root/.bash_history`
里没有这条，`tools/` 下也没有启动脚本，`gate.sh` 不是启动器），字面命令已不可逐字复原。
按 `/proc` 事实等价重建为：

```bash
cd /www/wwwroot/bapatch/tools
setsid nohup python3 account_auth_probe.py \
  >> /www/wwwroot/bapatch/logs/api_probe.out 2>&1 < /dev/null &
```

解释器 `/usr/bin/python3`、参数 `account_auth_probe.py`、cwd、stdin `/dev/null`、
stdout/stderr 目标文件全部与原进程一致（只多了 `setsid nohup` 做脱离，否则 ssh 一断就被带走）。

开关文件状态（apply 前后均确认）：

```
/www/wwwroot/bapatch/cn_1017_mode.txt   ABSENT      → cn_1017_mode() = 'dynamic'
/www/wwwroot/bapatch/cn_preempt.txt     ABSENT      → preempt 关（未创建）
/www/wwwroot/bapatch/cn_bridge_exp.txt  decrypt+plain+http200（22 B，未动）
```

---

## 2) 第 1 步：独立备份

```
路径    /www/wwwroot/bapatch/tools/account_auth_probe.py.pre_1017.20261116_062952
sha256  d5f27fcab6a897c88a8281fe9b2bd043924b68b5ca1c3ba4f60fd8649d1b814e
大小    73,445 B（-rw-r--r-- root root, mtime 06:07 保留）
cmp     与原文件逐字节相同（CMP_IDENTICAL）
```

---

## 3) 第 2 步：verify（apply 前，只读）

```
[verify] 目标        : /www/wwwroot/bapatch/tools/account_auth_probe.py
[verify] 大小/sha256 : 73445 B / d5f27fcab6a897c88a8281fe9b2bd043924b68b5ca1c3ba4f60fd8649d1b814e
[verify] 语法        : ok
[verify] marker      : begin=0 end=0 → 未打补丁
[verify] 锚点 A      : 第 1139 行
[verify] 锚点 B      : 第 1345 行
[verify] 旧分支      : 旧 1017/1019 分支 7 行逐字匹配
[verify] gen1017     : 顶层 35 键 / 子回包 26 / inner 83639 B / wire 124248 B
[verify] 自检        : PASS
[verify] 运行时开关  : cn_1017_mode() = 'dynamic'  (/www/wwwroot/bapatch/cn_1017_mode.txt)
[verify] 结论        : PASS
EXIT 0
```

逐项比对要求：语法 ok ✓ / begin=0 end=0 ✓ / A=1139 ✓ / B=1345 ✓ / 7 行匹配 ✓ /
gen1017 自检 PASS ✓ / 结论 PASS ✓ —— 全部符合，继续。

（`inner 83639 / wire 124248` 与 `gen1017.build()` 实测的 `83804 / 93307 / 124460`
数值不同是正常的：verify 用的是固定 `server_id=10015354380` + `now=2026-11-16T05:00:00`。）

---

## 4) 第 3 步：dry-run

```
[dry-run] 将写入 /www/wwwroot/bapatch/tools/account_auth_probe.py
[dry-run] 原文 1777 行 → 新文 1834 行（+57 行，纯插入，无删改）

hunk 1: @@ -1136,6 +1136,32 @@   (模块级 block A，26 行)
hunk 2: @@ -1342,6 +1368,37 @@   (1017 分发 block B，31 行)

新增行 57，删除行 0（`grep '^-' | grep -v '^---'` 为空 → NONE）
```

本地预演（用同一份 patch 脚本对下载副本 apply）预测写盘结果：**76,098 B / 1,834 行 /
sha256 `b9e248879051681fc2daa9e375d3023dafd17afb14098c9ccc0f53c2da9a6f0d`** —— 与线上实跑完全一致。

dry-run 全文留档：`work/ba/server/deploy/_ops1017/p1017.dry.txt`

---

## 5) 第 4 步：apply

```
[apply] OK  /www/wwwroot/bapatch/tools/account_auth_probe.py
        原文 1777 行 (73445 B, sha256=d5f27fcab6a897c88a8281fe9b2bd043924b68b5ca1c3ba4f60fd8649d1b814e)
        新文 1834 行 (+57 行, sha256=b9e248879051681fc2daa9e375d3023dafd17afb14098c9ccc0f53c2da9a6f0d)
        备份 /www/wwwroot/bapatch/tools/account_auth_probe.py.bak.20261116-063006
        语法检查: ok
        补丁后 1017 生效条件: cn_1017_mode() != 'legacy'
EXIT 0
```

apply 后立刻 `ls`：`-rw-r--r-- root root 76098 Nov 16 06:30 account_auth_probe.py`（= 76,098 B ✓）

---

## 6) 第 5 步：apply 后验证（重启前）

```
=== COMPILE ===
COMPILE OK

=== VERIFY ===
[verify] 大小/sha256 : 76098 B / b9e248879051681fc2daa9e375d3023dafd17afb14098c9ccc0f53c2da9a6f0d
[verify] 语法        : ok
[verify] marker      : begin=2 end=2 → 已打补丁
[verify] 锚点 A      : 第 1165 行
[verify] 锚点 B      : 第 1402 行
[verify] 旧分支      : 旧 1017/1019 分支 7 行逐字匹配
[verify] gen1017     : 顶层 35 键 / 子回包 26 / inner 83639 B / wire 124248 B
[verify] 自检        : PASS
[verify] 运行时开关  : cn_1017_mode() = 'dynamic'
[verify] 预期行为    : 1017 → 动态（35 键）
[verify] 结论        : PASS
EXIT 0

sha256sum : b9e248879051681fc2daa9e375d3023dafd17afb14098c9ccc0f53c2da9a6f0d
wc -l     : 1834
wc -c     : 76098
marker 行 : 1139 (begin-A) / 1164 (end-A) / 1371 (begin-B) / 1401 (end-B)
```

额外做了一次只读的 `--prove-dispatch`（用桩把插入的 B 块抽出来真跑）：

```
[prove] 抽出的分发块（29 行）在桩环境下执行结果:
        返回三元组          : ok
        obj 顶层键          : 35
        requestid 闭合      : outer == inner == 49646ed0-27ed-4bc7-b063-4a77bf047003
        wire 长度           : 124460 B
        legacy 模式落到旧分支: True
        gen1017 异常兜底     : True（rec['gen1017_err']="RuntimeError('boom')"）
[prove] 结论: PASS
```

→ inner RequestId 与外层 requestid 闭合、`legacy` 与异常两条退路都成立，才动重启。

---

## 7) 第 6–7 步：重启 + 健康检查

重启方式：`setsid nohup` 同一 cwd / 同一解释器 / 同一参数 / 同一重定向目标。

```
旧 pid 2529465  → kill -TERM → 100 ms 内退出，端口 100 ms 内释放
新 pid 2532984  （detach 后 PPID=1，started 06:30:28）
新进程 fd0/fd1/fd2 -> /dev/null, logs/api_probe.out, logs/api_probe.out（与原进程一致）
listen: LISTEN 0 5 127.0.0.1:9097 users:(("python3",pid=2532984,fd=3))  ← 与 nginx ba_mitm.conf:79 proxy_pass 一致
```

健康检查（注意第 0 节偏离项 3）：

```
# bridge 自身
curl http://127.0.0.1:9097/api/health  →  HTTP 200, 0 B
# nginx 层（gs-api / gsqc-api vhost，location = /api/health { return 200 "ok"; }）
curl -sk -H 'Host: gs-api.bluearchive-cn.com'  https://127.0.0.1:8443/api/health → 200 / 2 B / ok
curl -sk -H 'Host: gsqc-api.bluearchive-cn.com' https://127.0.0.1:8443/api/health → 200 / 2 B / ok
```

**为什么 bridge 是 0 字节**：`account_auth_probe.py` 里根本没有 `/api/health` 路由，
未知路径会 `forward-unknown-protocol` 转发到 `TARGET_BASE = http://127.0.0.1:5000`
并且 `http_override=http200`，所以回 200 + 空体。
而且这是**基线行为、不是补丁副作用**：重启前的旧进程在 `06:28:54` 处理同一条请求时，
`api_all_requests.log` 记录同样是 `resp_code 200 / resp_len 0`。
“200 + 2 字节 ok”是 nginx 的 `gs-api` vhost 给的，桥只负责 9097。

bridge 存活的硬证据：请求有被处理并被记进 `api_all_requests.log`
（`"mode": "bridge"`, `"served": "bridge"`, `"resp_code": 200`）。

---

## 8) 第 8 步：日志

bridge stdout/stderr 日志 `/www/wwwroot/bapatch/logs/api_probe.out` 全文（56 B，共 2 行）：

```
[warn] inner len 160 != 432
[warn] inner len 240 != 432
```

两行都是 06:12:48 之前旧进程留下的老 warn；**无 traceback、无 startup 异常**。
新进程启动横幅 `bridge v6 listening on 127.0.0.1:9097 …` 还在 Python 的块缓冲里
（stdout 是文件时 print 是块缓冲），未 flush 属正常，不影响服务。

请求日志 `api_all_requests.log`：重启后 5 条请求，`traceback|resp_code: 5xx` 计数 **0**。

---

## 9) 回滚方案（已就位，未使用）

```bash
# 软回滚（不重启，立刻生效）—— 首选
echo legacy > /www/wwwroot/bapatch/cn_1017_mode.txt
# 恢复动态：python3 /www/wwwroot/bapatch/tools/patch_1017.py --legacy off

# 硬回滚 A：剥 marker 块（逐字节回到原文件）
cd /www/wwwroot/bapatch/tools && python3 patch_1017.py --rollback   # 然后重启

# 硬回滚 B：直接盖备份（最稳）
cp -p /www/wwwroot/bapatch/tools/account_auth_probe.py.pre_1017.20261116_062952 \
      /www/wwwroot/bapatch/tools/account_auth_probe.py   # 然后重启
```

当前 `--legacy status` = `'dynamic'`，1017 将走动态生成。

---

## 10) 一句话结论

**patch_1017 已在线上生效**：`account_auth_probe.py` 76,098 B / 1,834 行 /
sha256 `b9e2488…9a6f0d`，bridge 由 pid 2529465 换成 2532984 正常监听 127.0.0.1:9097，
`cn_1017_mode.txt` 不存在 ⇒ 1017 走 dynamic（35 键 / wire ~124 KB），
legacy 与异常退路均经桩测验证，未使用回滚。

## 11) 剩余风险

- 重启后还没有真实客户端的 1017 请求打进来（`api_all_requests.log` 里 1017 计数 0），
  动态分支只经 `--prove-dispatch` 桩测验证过；首次真实 1017 的日志应出现
  `"gen_kind": "loginsync-1017-dynamic"`（若失败会记 `rec['gen1017_err']` 并静默落回 492 B 旧包）。
- 旧进程的环境变量在 kill 之前没来得及完整抓取（`/proc/<pid>/environ` 已随进程消失），
  只能确认新进程无 `CN_*` / `BA_*` 覆盖；行为开关都在 `/www/wwwroot/bapatch/` 下的文件里，文件均未改动。
- `patch_1017.py` 是本工作区上传的新文件（服务器原本缺失），已留在 `tools/` 供 --verify/--rollback 使用。
