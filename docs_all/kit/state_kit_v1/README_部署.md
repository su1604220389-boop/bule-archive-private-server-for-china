# 碧蓝档案国服 · 网关劫持部署手册（state_kit_v1）

> 目标：让 `com.RoamingStar.BlueArchive` 3.0.2 把业务请求打到我们自己的网关
> `http://127.0.0.1:5000/api/`，而不是官方 `https://gsqc-api.bluearchive-cn.com/api/`。
>
> 本 kit 只做「把客户端指过去」这一段：改缓存文件 + 让 `state` 请求失败 + 用代理取证。
> 5000 端口上的网关本体不在本 kit 范围内。

---

## 0. 为什么这条路能走通

三条已经实测过的前提（来自 lead，直接使用，不重新推导）：

1. 客户端网关地址的**唯一来源**是 `GET https://state-api.bluearchive-cn.com/api/state`，
   官方响应：

   ```
   {"Servers":["https://gsqc-api.bluearchive-cn.com/api/","https://gs-api.bluearchive-cn.com/api/"],"State":1,"Msg":"服务器维护中，请耐心等待开服！"}
   ```

2. `res/Dk.xml` 里 `cleartextTrafficPermitted=true`（全域名允许明文）→ 只要 `Servers`
   给的是 `http://`，后面整条业务链路都**不需要 TLS**。
3. `/sdcard/Android/data/com.RoamingStar.BlueArchive/files/Hosts` 是上面 `Servers` 的落盘缓存
   （官方给 2 个服务器，文件里正好 2 条），格式已完整解出（见附录 A）。

于是部署由两半组成：

* **改缓存**：把两条记录的 `url` 从 `https://gsqc-api.bluearchive-cn.com:443` 改成
  `http://127.0.0.1:5000/api/`，其余字节（`mid` / `u64` / `flag`）原样保留；
* **让 `state` 失败**：只要 `/api/state` 拿不到官方响应，客户端就用缓存（三种做法见第 6 节）。

---

## 1. 文件清单

```
kit\state_kit_v1\
├─ hosts_tool.py                       Hosts 文件解析 / 生成 / 克隆（纯标准库）
├─ samples\hosts_sample.bin            166 字节真实样本（sha256 b0e5a205…2f25）
├─ out\hosts_127.bin                   可直接刷的成品：url=http://127.0.0.1:5000/api/（142 B）
├─ out\hosts_lan_192.168.0.2.bin       局域网版：url=http://192.168.0.2:5000/api/（146 B）
├─ pc\
│  ├─ state_gw.py                      CONNECT 代理 + 自签 TLS 终止 + 假 /api/state
│  ├─ make_certs.ps1                   生成 CA + leaf 证书（openssl）
│  ├─ coalesce_probe.py                CONNECT 与 ClientHello 同包到达的回归探针
│  ├─ selftest.ps1                     端到端自测（29 项断言）
│  ├─ certs\                           由 make_certs.ps1 生成
│  └─ logs\                            按 host 分目录的原始报文
├─ phone\
│  └─ hosts_install.sh                 手机上跑的备份 / 校验 / 写入 / 还原脚本
└─ README_部署.md                      本文件
```

`kit\BA_probe_kit_v1\` 是上一版探针，**没有被修改**（本次新增文件全部在 `kit\state_kit_v1\`）。

---

## 2. 前置条件

| 东西 | 要求 | 本次验证环境 |
|---|---|---|
| PC | Windows + PowerShell 5.1+ | Windows 11 / PowerShell 5.1.26100.9818 |
| Python | 3.8+（用到 f-string 之外都是标准库） | 3.12.11 |
| curl | 可选，仅自测用 | 8.22.0 |
| openssl | 仅 `--mode tls` 需要 | OpenSSL 3.5.2（msys2 ucrt64） |
| 手机 | 已跑过一次游戏（`files/` 目录存在），最好有 root | 本次未接触真机 |

自检一把：

```powershell
cd C:\Users\su\Desktop\大肥鱼项目\BAServer\kit\state_kit_v1
python hosts_tool.py selftest --tmp _tmp
```

---

## 3. 第 0 步：先备份（两处，都要）

### 3.1 PC 侧：确认样本能解析

```powershell
python hosts_tool.py parse samples\hosts_sample.bin
```

### 3.2 手机侧：备份当前文件

```powershell
adb push kit\state_kit_v1\phone\hosts_install.sh /data/local/tmp/
adb shell "sh /data/local/tmp/hosts_install.sh --check"
adb shell "sh /data/local/tmp/hosts_install.sh --backup"
```

`--backup` 会：

* 拷到 `/sdcard/ba_hosts_bak_<YYYYmmdd_HHMMSS>.bin`
* 打印字节数 + **sha256**，并与源文件比对（不一致直接报错退出）

> 权限：`/sdcard/Android/data/<包名>/files/` 在 Android 11+ 属于应用私有目录。
> `adb shell` 大多数机型能读写；报 `Permission denied` 时改用
> `adb shell su -c "sh /data/local/tmp/hosts_install.sh --backup"`。

### 3.3 再留一份「原始 166 字节」在家里

把备份拉回 PC，顺便算一次 hash 存档：

```powershell
adb pull /sdcard/ba_hosts_bak_20261114_002143.bin .\ba_hosts_orig.bin
python hosts_tool.py parse .\ba_hosts_orig.bin
```

---

## 4. 第 1 步：生成要写进去的 Hosts

**首选 `clone`**：读真实样本，只改 `url`，长度前缀自动重算，`mid/u64/flag` 一个字节都不动。

```powershell
cd C:\Users\su\Desktop\大肥鱼项目\BAServer\kit\state_kit_v1

# 手机本机有 5000（或已做 adb reverse）
python hosts_tool.py clone samples\hosts_sample.bin out\hosts_127.bin `
    --set-url 0=http://127.0.0.1:5000/api/ `
    --set-url 1=http://127.0.0.1:5000/api/
```

产物 142 字节，`sha256 ad9d77e86f01284013123b2dcdaeb1afa30ab1cb4203cf7fa160c53b592fdebc`。

局域网版（5000 跑在 PC 上、手机走 Wi-Fi）：

```powershell
python hosts_tool.py clone samples\hosts_sample.bin out\hosts_lan_192.168.0.2.bin `
    --set-url 0=http://192.168.0.2:5000/api/ `
    --set-url 1=http://192.168.0.2:5000/api/
```

> `0` / `1` 是条目序号，用 `parse` 看到的顺序。
> 想改 `host` 字段（一般不要改）：加 `--set-host 0=example.com`。

**如果样本丢了**（比如手机上的 `Hosts` 已经被覆盖），用 `build` 从零构造：

```powershell
python hosts_tool.py build out\hosts_custom.bin `
    --entry "gsqc-api.bluearchive-cn.com=http://127.0.0.1:5000/api/" `
    --entry "gs-api.bluearchive-cn.com=http://127.0.0.1:5000/api/" `
    --u64-hex 92dd898bf240df48,103b97d83e41df48 `
    --flag 1
```

本次已验证：对同样的输入，`build` 与 `clone` 的输出**逐字节相同**
（都是 `ad9d77e8…debc`），所以两条路等价；但有真样本时仍然用 `clone`，
因为它能保住我们还没完全确定语义的字段。

---

## 5. 第 2 步：写入手机

```powershell
adb push kit\state_kit_v1\out\hosts_127.bin /data/local/tmp/hosts_127.bin
adb shell "sh /data/local/tmp/hosts_install.sh --install /data/local/tmp/hosts_127.bin"
```

`--install` 会依次做：

1. **校验**候选文件（版本、count、每条 hostlen/urllen、opaque 8 字节、flag、总长度必须恰好用完）；
2. 自动把当前文件再备份一份（防止手抖）；
3. `cat 候选 > 目标`（原地截断写，保留路径/属主）；
4. 打印 **BEFORE / AFTER 十六进制**；
5. 回读目标文件重新解析并比对 sha256，不一致直接非零退出。

失败退出码：`1` 一般错误，`2` 文件不是合法 Hosts。**校验不过绝不写盘**（已测）。

> 写入后如果客户端读不到文件，看属主：`ls -l .../files/Hosts`。
> 用 root 写有时会把属主改成 root，必要时 `chown u0_aXXX:u0_aXXX`，
> 或改用 `su -c 'cat /data/local/tmp/hosts_127.bin > .../Hosts'` 后 `restorecon`。

---

## 6. 第 3 步：让 `/api/state` 请求失败（三选一）

原理：客户端只有在**拿不到**官方 `state` 时才会回退到本地缓存。
所以「改缓存」必须配「掐 state」，否则客户端每次都拿官方 `Servers` 把我们覆盖掉。

### 方式 A：飞行模式（最干净，全离线）

* 开飞行模式（Wi-Fi + 移动数据全关）。
* `127.0.0.1` 是 loopback，**不依赖任何网络**，照样能连。
* 要求：5000 服务必须跑在**手机本机**，或者用 USB 线做 `adb reverse`（USB 在飞行模式下依然工作）。

适合：手机端直接跑网关；只想让客户端离线登录。

### 方式 B：只掐 `state-api`，其它网络照常

B1（root，推荐）：让域名解析到黑洞

```powershell
adb shell su -c "mount -o rw,remount /system 2>/dev/null; echo '127.0.0.1 state-api.bluearchive-cn.com' >> /system/etc/hosts"
```

B2（root）：按 IP 丢包（CDN 多 IP 时多来几条）

```powershell
adb shell su -c "ping -c1 state-api.bluearchive-cn.com"
adb shell su -c "iptables -I OUTPUT -p tcp -d <IP> --dport 443 -j REJECT"
```

B3（不动手机）：在路由器 / 上游 DNS 上把 `state-api.bluearchive-cn.com` 指到 `0.0.0.0`。

适合：5000 跑在 PC 上（`out\hosts_lan_<PC_IP>.bin`），手机还要用别的网络。

### 方式 C：本地 TLS 代理（还能顺便取证）

```powershell
cd kit\state_kit_v1\pc
powershell -NoProfile -ExecutionPolicy Bypass -File .\make_certs.ps1     # 首次
python state_gw.py --mode tls --port 7890 `
    --only-hosts state-api.bluearchive-cn.com,gsqc-api.bluearchive-cn.com,*.bluearchive-cn.com `
    --reply-file reply_state.json
```

`reply_state.json`（自定义响应，逐请求重新读盘，改完即生效）：

```json
{"Servers":["http://127.0.0.1:5000/api/"],"State":0,"Msg":""}
```

手机：Wi-Fi → 代理 → 手动 → `PC_IP:7890`。两种结果**都能用**：

| 手机是否装了我们的 CA | 代理日志 | 结果 |
|---|---|---|
| 不装 | `TLS-REJECT` | 握手失败 → `state` 失败 → 客户端回退缓存 ✅ |
| 装（可选） | `TLS-OK` + `FAKE-STATE` | 直接返回我们的 JSON，连缓存都不需要 ✅ |

白名单之外的一切 CONNECT 直接 `502`（防止误伤其它流量）；`http://127.0.0.1:5000/...`
这类**明文**请求会像正常代理一样转发出去，不会被吞成 `{}`。

---

## 7. 第 4 步：把 5000 接上

| 部署形态 | 用的 Hosts | 额外动作 |
|---|---|---|
| 网关跑在手机本机 | `out\hosts_127.bin` | 无 |
| 网关跑在 PC，USB 连接 | `out\hosts_127.bin` | `adb reverse tcp:5000 tcp:5000` |
| 网关跑在 PC，走 Wi-Fi | `out\hosts_lan_<PC_IP>.bin` | PC 防火墙放行 TCP 5000 |

`adb reverse` 最稳：手机上的 `127.0.0.1:5000` → PC 的 5000，且不受 Wi-Fi 网段影响。

---

## 8. 第 5 步：怎么判定成功

**判定标准：客户端后续业务请求打到我们指定的 `http://127.0.0.1:5000/api/`，而不是官方。**

按证据强度排序：

1. **5000 侧访问日志**（最硬）：出现 `GET /api/...`、`POST /api/...`，
   `Host` 是 `127.0.0.1:5000` 或 `PC_IP:5000`，并带客户端的 `User-Agent`。
2. **代理侧日志**（方式 C）：`pc\logs\<host>\index.txt` 里请求持续出现，
   且 5000 侧同时有流量；`logs\session_*.log` 里有 `FAKE-STATE` / `TLS-OK`。
3. **抓包**：`adb shell su -c "tcpdump -i any -n port 5000"`（需 tcpdump），
   或 PC 上 Wireshark 过滤 `tcp.port == 5000`。
4. **反面证据**：5000 一直没请求、客户端却还能正常进游戏 → 说明还在走官方，
   即 `state` 没失败 / 缓存没生效，回到第 6 步。

辅助信号：

* 客户端弹「服务器维护中，请耐心等待开服！」→ 我们返回的 `State` 是 `1`（假 JSON 里改 0 即可）。
* 客户端能过登录/进大厅，但 5000 上全是 `404` → 说明**已经指过来了**，只是网关本体还没实现该接口。

---

## 9. 回滚

```powershell
# 手机侧最近一次备份
adb shell "sh /data/local/tmp/hosts_install.sh --restore"

# 指定某个备份
adb shell "sh /data/local/tmp/hosts_install.sh --restore /sdcard/ba_hosts_bak_20261114_002143.bin"
```

再撤掉辅助手段：关 Wi-Fi 代理、删 `/system/etc/hosts` 里那行、`iptables -D OUTPUT ...`。
若客户端还缓存着坏文件，清一次应用数据或重进游戏即可。

---

## 10. 已验证（全部在本机实跑，输出为原文摘录）

环境：Windows 11 / PowerShell 5.1.26100.9818 / Python 3.12.11 / curl 8.22.0 /
OpenSSL 3.5.2 / dash（msys2）。**没有接触任何手机。**

### 10.1 `hosts_tool.py`：166 字节向量解析 + 自测

```
$ python hosts_tool.py parse samples\hosts_sample.bin
size          : 166 bytes
sha256        : b0e5a2052ebcb46a84d1eb28665c0cfbc2565ed959cb5b678369422599962f25
version       : 1  (u32 LE @0x00000000 = 01000000)
count         : 2  (u32 LE @0x00000004 = 02000000)
--- entry[0] ---
  host_off    : 0x00000008  hostlen=27
  host        : gsqc-api.bluearchive-cn.com
  mid_off     : 0x00000024  mid=0x01000000  (u32 LE = 1)
  url_off     : 0x00000028  urllen=39
  url         : https://gsqc-api.bluearchive-cn.com:443
  opaque_off  : 0x00000050
  opaque_hex  : 92dd898bf240df48
  opaque_le   : 0x48df40f28b89dd92  (5250987101004619154)
  opaque_be   : 0x92dd898bf240df48  (10582765933548330824)
  flag_off    : 0x00000058  flag=0x01
--- entry[1] ---
  host_off    : 0x00000059  hostlen=25
  host        : gs-api.bluearchive-cn.com
  ...
  opaque_hex  : 103b97d83e41df48
  opaque_le   : 0x48df413ed8973b10  (5250987428714855184)
--- self check ---
  [ok] header + entries = 166 bytes, file = 166 bytes
  [ok] count field matches parsed entries (2)
  [ok] version == 1
  [ok] entry[0] length prefixes match payload
  [ok] entry[1] length prefixes match payload
  => PASS
```

> 顺带一个观察：两条 `opaque` 按 **little endian** 读分别是
> `0x48df40f28b89dd92` 与 `0x48df413ed8973b10`，高 32 位都是 `0x48df40f2/0x48df413e`
> （同一时间窗），低 32 位不同 —— 与「时间/版本戳」的判断一致。

```
$ python hosts_tool.py selftest --tmp _tmp
  [ok] vector is 166 bytes
  [ok] parse -> build is byte identical
  [ok] clone url changed
  [ok] clone kept mid
  [ok] clone kept opaque
  [ok] clone kept flag
  [ok] clone length recomputed
  [ok] clone entry1 body byte identical except host
  [ok] random#0 (n=1, 89 bytes) round trip
  [ok] random#1 (n=6, 437 bytes) round trip
  [ok] random#2 (n=5, 361 bytes) round trip
  [ok] random#3 (n=1, 45 bytes) round trip
  [ok] random#4 (n=1, 89 bytes) round trip
  [ok] reject truncated
  [ok] reject count too big
  [ok] reject trailing garbage
  [ok] reject empty
  [ok] reject hostlen zero

SELFTEST PASSED: 1 vector + 1 clone case + 5 random round trips + 5 negative cases
```

`build` 与 `clone` 交叉验证：

```
wrote _tmp\build1.bin (142 bytes, 2 entries)
build==clone: True 142 142
_tmp\build1.bin    ad9d77e86f01284013123b2dcdaeb1afa30ab1cb4203cf7fa160c53b592fdebc
_tmp\hosts_ours.bin ad9d77e86f01284013123b2dcdaeb1afa30ab1cb4203cf7fa160c53b592fdebc
```

### 10.2 `pc\state_gw.py`：`selftest.ps1` 29 项全绿

```
$ powershell -NoProfile -ExecutionPolicy Bypass -File .\selftest.ps1
[0] certs
  [ok]   certs\leaf.crt exists
  [ok]   certs\leaf.key exists

[1] mode=logonly (port 17890)
  [ok]   gateway listening
  [ok]   CONNECT answered with 502
  [ok]   log has CONNECT gsqc-api.bluearchive-cn.com:443
  [ok]   log has LOGONLY tag
  [ok]   per-host raw dump logs/<host>/*.raw
  [ok]   raw dump starts with CONNECT

[2] mode=tls (port 17891, self-signed leaf, --only-hosts, --reply-file)
  [ok]   GET /api/state served from --reply-file
  [ok]   GET body points at our gateway
  [ok]   POST /api/state served too
  [ok]   response has Server header
  [ok]   response has Date header
  [ok]   response has Content-Length
  [ok]   second whitelisted host works
  [ok]   plain http absolute-URI /api/state served
  [ok]   non-whitelisted CONNECT -> 502
  [ok]   log has TLS-OK
  [ok]   log has FAKE-STATE
  [ok]   log has POST request
  [ok]   log has BLOCK for example.com
  [ok]   per-host raw dumps for gsqc-api
  [ok]   per-host raw dumps for state-api

[3] CONNECT + ClientHello in one TCP segment
  [ok]   coalesced handshake succeeds
  [ok]   log has TLS-PRE (leftover injected)

[4] plain HTTP relay (proxied loopback traffic must not be swallowed)
  [ok]   proxied loopback request is relayed
  [ok]   log has FWD to 127.0.0.1:17899

 RESULT: 29 passed, 0 failed
 ALL CHECKS PASSED
```

### 10.3 内置假 `state`（不经 `--reply-file`）

```
$ curl.exe -k -sS -D - -x http://127.0.0.1:17892 https://state-api.bluearchive-cn.com/api/state
HTTP/1.1 200 Connection established

HTTP/1.1 200 OK
Server: BAStateGW/1.1
Date: Fri, 13 Nov 2026 16:22:54 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 189
Connection: close

{"Servers": ["http://127.0.0.1:5000/api/"], "State": 0, "Msg": "", "CallbackUrl": "", "CustomerServiceUrl": "", "AddressablesCatalogUrlRoots": ["https://static.bluearchive-cn.com/prodm39"]}
```

网关日志（`logs\<host>\` 按 host 分文件落盘）：

```
[00:22:54.744] CONNECT    state-api.bluearchive-cn.com:443
[00:22:54.745] RAW        state-api.bluearchive-cn.com -> state-api.bluearchive-cn.com\20261114_002254_0001_CONNECT_443.raw (148 bytes)
[00:22:54.749] TLS-OK     state-api.bluearchive-cn.com  version=TLSv1.3 alpn=http/1.1 cipher=('TLS_AES_256_GCM_SHA384', 'TLSv1.3', 256)  <-- client accepted our cert
[00:22:54.750] REQUEST    state-api.bluearchive-cn.com  GET /api/state HTTP/1.1  (101 hdr, 0 body)  path=/api/state
[00:22:54.751] RAW        state-api.bluearchive-cn.com -> state-api.bluearchive-cn.com\20261114_002254_0002_GET__api_state.raw (101 bytes)
[00:22:54.751] FAKE-STATE GET state-api.bluearchive-cn.com /api/state  (builtin) -> {"Servers": ["http://127.0.0.1:5000/api/"], ...}
```

### 10.4 `phone\hosts_install.sh`：dash + bash --posix 双解释器跑通

用 `BA_HOSTS` / `BA_BAK_DIR` 把路径重定向到 PC 临时目录，**脚本本体不做任何改动**：

```
$ dash run_test.sh          # 0.9 KB 目录里，用 166B 样本当 Hosts
========== 0. syntax check ==========
[ok] sh -n
========== 1. --check on the real 166-byte sample ==========
...
   [ok] structure consistent: 8 + entries = 166 bytes
hash: sha256:b0e5a2052ebcb46a84d1eb28665c0cfbc2565ed959cb5b678369422599962f25
[ok] rc=0
========== 2. --install a 142-byte file pointing at 127.0.0.1:5000 ==========
   [ok] structure consistent: 8 + entries = 142 bytes
[*] backup written: ./ba_hosts_bak_20261114_002143.bin
[*]   bytes : 166
[*]   hash  : sha256:b0e5a205...2f25
[*]   same as live file: yes
[*] writing install_src.bin -> Hosts
--- AFTER: Hosts (142 bytes) ---
000000 01 00 00 00 02 00 00 00 1b 67 73 71 63 2d 61 70  >.........gsqc-ap<
...
000040 70 69 2f 92 dd 89 8b f2 40 df 48 01 19 67 73 2d  >pi/.....@.H..gs-<
...
[*] installed ok
[*]   bytes : 142
[*]   hash  : sha256:ad9d77e8...debc
[ok] rc=0
========== 6. --install a broken file must be refused with rc=2 ==========
[x] entry[1]: opaque field truncated (want 16 hex chars, got 12)
[ok] rc=2
========== 8. --restore the ORIGINAL 166-byte backup (explicit path) ==========
[*] installed ok
[*]   bytes : 166
[*]   hash  : sha256:b0e5a205...2f25
[ok] rc=0
RESULT: rc_all=0
```

同一套用例在 `bash --posix` 下：`RESULT: rc_all=0`，11 个步骤全 `[ok]`。

### 10.5 已修掉的真实问题（v1 → v2）

| # | 问题 | 位置 | 影响 |
|---|---|---|---|
| 1 | 响应头少了结尾空行 `\r\n` | `http_response()` | 所有响应都不完整，curl 报 `Proxy CONNECT aborted` |
| 2 | CONNECT 与 ClientHello 同包时后半段被丢弃 | `handle_client` / 新增 `TLSChan` | 真实客户端偶发 `record layer failure` |
| 3 | `unwrap()` 抛 `SSLWantReadError` 时 close_notify 没发出去 | `TLSChan.close()` | 客户端报 `missing close_notify` |
| 4 | `state` 只按 `path in target` 匹配，没处理 query / POST / 明文代理 | `is_state_path()` / `serve_plain_http()` | POST 与 `?x=1` 漏匹配 |
| 5 | 明文请求一律回 `{}` | `serve_plain_http()` | 部署后 `http://127.0.0.1:5000/...` 会被代理吞掉 |
| 6 | 没有白名单 | `--only-hosts` | 代理会替所有域名握手，误伤面太大 |
| 7 | 无 `Server`/`Date` | `http_response()` | 部分 HTTP 栈缺头告警 |
| 8 | 请求不落盘 | `dump_request()` | 事后无法复查原始字节 |
| 9 | `tunnel` 模式丢掉 CONNECT 同包的 payload | `handle_tunnel()` | 隧道首包丢失 |
| 10 | cert 默认相对路径依赖 cwd | `--cert/--key` 默认值 | 换目录启动就找不到证书 |

---

## 11. 只能在真机上验证的环节

下面这些本 kit **没有**验证（没有手机），上线时按顺序确认：

1. 客户端是否真的在 `state` 失败后读取并使用这个 `Hosts` 缓存（我们只验证了文件格式与写入路径）。
2. Android 11+ 对 `/sdcard/Android/data/<包名>/files/` 的写权限与属主（`adb shell` vs `su`）。
3. 客户端是否接受 `http://` 明文网关（依据是 `Dk.xml` 的 `cleartextTrafficPermitted=true`，未真机回归）。
4. 客户端是否对 `host` 字段做额外校验（我们只改了 `url`，`host` 保持官方值；如需可 `--set-host`）。
5. 缓存的生效时机：重启 App / 杀进程 / 清数据 哪个才触发重读。
6. 装了自签 CA 后 Unity/OkHttp 是否接受（不装 CA 的「握手失败 → 回退缓存」路径不受影响）。

---

## 附录 A：`Hosts` 格式

```
u32  version            = 01 00 00 00
u32  count              = 02 00 00 00
loop count times:
    u8   hostlen
    u8[hostlen] host     "gsqc-api.bluearchive-cn.com" (27)
    u32  mid             = 01 00 00 00
    u8   urllen
    u8[urllen]  url      "https://gsqc-api.bluearchive-cn.com:443" (39)
    u64  opaque          8 字节原样，如 92 dd 89 8b f2 40 df 48
    u8   flag            = 01
```

166 字节样本（sha256 `b0e5a205…2f25`）：

```
01000000 02000000 1b 677371632d6170692e626c7565617263686976652d636e2e636f6d 01000000 27 68747470733a2f2f677371632d6170692e626c7565617263686976652d636e2e636f6d3a343433 92dd898bf240df48 01
19 67732d6170692e626c7565617263686976652d636e2e636f6d 01000000 25 68747470733a2f2f67732d6170692e626c7565617263686976652d636e2e636f6d3a343433 103b97d83e41df48 01
```

改 `url` 时必须**重算**该条目的 `urllen`，`count` 不变；`u64` / `flag` / `mid` 原样拷贝
（`clone` 自动满足）。

---

## 附录 B：命令速查

### `hosts_tool.py`

```powershell
python hosts_tool.py parse <file> [--json]
python hosts_tool.py build <out> --entry HOST=URL [--entry ...] [--u64-hex HEX[,HEX]] [--flag N[,N]] [--mid-hex HEX] [--version N]
python hosts_tool.py clone <src> <out> [--set-url IDX=URL] [--set-host IDX=HOST] [--set-u64-hex IDX=HEX] [--set-flag IDX=N]
python hosts_tool.py selftest [--tmp DIR] [--seed N]
```

### `pc\state_gw.py`

```powershell
python state_gw.py --mode logonly|passthrough|tls --port 7890
    [--only-hosts a,b,*.c]
    [--reply-file reply.json]
    [--servers http://127.0.0.1:5000/api/] [--state 0] [--state-msg ""] [--catalog URL]
    [--cert certs\leaf.crt] [--key certs\leaf.key] [--logdir logs] [--bind 0.0.0.0] [--debug]
```

日志：`logs\session_*.log` 汇总；`logs\<host>\<ts>_<seq>_<METHOD>_<path>.raw` 单请求原文；
`logs\<host>\index.txt` 索引。

### `phone\hosts_install.sh`

```sh
sh hosts_install.sh --check
sh hosts_install.sh --backup
sh hosts_install.sh --install <file>
sh hosts_install.sh --restore [<file>]
sh hosts_install.sh --hex [<file>]
```

---

## 附录 C：坑

* **count 写错**：少写/多写会让客户端解析越界；`install` 会拒绝，但 `build` 手改时注意。
* **url 长度 > 255**：单字节长度，超了直接报错。`http://192.168.0.2:5000/api/` 才 30 字节，绰绰有余。
* **地址写 `localhost`**：客户端可能走 IPv6 的 `::1` 而服务只监听 IPv4，尽量写 `127.0.0.1`。
* **只改缓存不掐 state**：客户端拿到官方 `Servers` 会重新覆盖，白改。
* **改了缓存不清 App**：部分机型缓存常驻内存，需要杀进程重进。
* **PowerShell 5.1 跑自测**：脚本里所有原生命令都走 `cmd /c`，否则 `$ErrorActionPreference="Stop"` 会因 curl 的 stderr 误抛。
* **`--only-hosts` 用 glob**：`*.bluearchive-cn.com` 是 fnmatch 语法，别写成正则。
