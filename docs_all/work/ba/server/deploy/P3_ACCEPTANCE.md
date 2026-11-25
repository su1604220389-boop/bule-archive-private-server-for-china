# 协议 3（`api/networktime/sync` = `NetworkTime_Sync`）上线验收口径

写于 2026-11-17 01:1x。作者：Lead。**本文件是唯一验收依据**，与 `patch_3.py` / `PROGRESS_3_NETWORKTIME.md` 互补：那两份讲怎么做，这份讲怎么判。

---

## 0. 唯一权威 fixture

`report\_tmp\official_decoded_201\04_3_api_networktime_sync.response.json`（1,034 B，官方抓包 id=88，北京时间 04:30:55.625）

```json
{
  "Protocol": 3,
  "SessionKey": {
    "AccountServerId": 10015354380,
    "MxToken": "Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA"
  },
  "ServerTimeTicks": 639304002554622705,
  "ServerNotification": 0,
  "RequestId": "d1d5579c-9c2b-44e6-a496-c66d4ccca10c",
  "ReceiveTick": 639304002554622693,
  "EchoSendTick": 639304002554622693
}
```

外层 wire（`plain` 字段原文）：

```
{"protocol":"NetworkTime_Sync","packet":"<上面这串 inner JSON 的转义结果>","requestid":"d1d5579c-9c2b-44e6-a496-c66d4ccca10c"}
```

`meta`：`status=200`、`resp_bytes=620`、`protocol=3`

### 从 fixture 直接读出、此前未落盘的不变量

| # | 不变量 | 数值 |
|---|---|---|
| a | `ReceiveTick == EchoSendTick` | `639304002554622693 == 639304002554622693` ✅ |
| b | `ServerTimeTicks - EchoSendTick` | **12** ticks（= 1.2 µs） |
| c | 键序（7 键） | `Protocol, SessionKey, ServerTimeTicks, ServerNotification, RequestId, ReceiveTick, EchoSendTick` |
| d | `SessionKey` 位置 | **第 2 位**（1002 的「SessionKey 排最后」例外**不适用**协议 3） |
| e | 外层 `requestid` == 内层 `RequestId` | ✅ 同一个 UUID |
| f | `MxToken` 长度 | **64 字符** base64（48 随机字节） |
| g | `RequestId` 形态 | 小写 UUIDv4，36 字符 |

`ServerTimeTicks` 是 .NET ticks（100 ns 自 0001-01-01），官方存 **UTC+8 墙钟**。

---

## 1. 现状（打补丁前）

线上 `gen_kind = min+base`，wire **536 B**，两个 tick 走通用空构造 ⇒ 客户端算出的时钟偏移是错的，所有倒计时/活动时间随之错乱。

> **红线**：协议 3 绝不能继续用通用空构造。两个 tick 必须是真值。

### 1.1 `gen3.py` 的 CLI 面（实测，`--help` exit 0）

```
--server-id          账号 AccountServerId
--now                固定时间（UTC）YYYY-MM-DDTHH:MM:SS
--request-id         缺省 = uuid4
--mxtoken            缺省 = 按 server_id 派生 64 字符 base64
--out / --compact / --wrap     输出控制（--wrap 输出 {"meta":…,"inner":…}）
--no-dto-check       跳过 dto_extra 键序校验
--recv-tick          ReceiveTick（.NET ticks），缺省 = 当前 ticks
--echo-tick          EchoSendTick，缺省 = 与 ReceiveTick 相同
--recv-offset-us     ReceiveTick 距 ServerTimeTicks 的微秒偏移，**缺省 0**
--official           直接用官方抓包本体（结构基准）
--verify-official    官方包回灌 + 逐字节比对
```

**注意 `--recv-offset-us` 缺省 0** ⇒ 默认产物 `ReceiveTick == ServerTimeTicks`，此时断言 6 的值为 **0**，与官方的 12 ticks 不同但功能等价（1.2 µs 完全是噪声）。**不要因此判失败。**

复现官方逐字节（314 B inner / 620 B wire）：`python3 gen3.py --verify-official`。

---

## 2. 验收清单（全过才算通过）

对**线上 9097** 的真实响应逐条判：

| # | 断言 | 判据 |
|---|---|---|
| 1 | HTTP 状态 | `200` |
| 2 | 外层 `protocol` | `== "NetworkTime_Sync"` |
| 3 | 外层 `requestid` | `==` 内层 `RequestId` |
| 4 | 内层键数量与顺序 | 7 个，顺序见 §0-c |
| 5 | `ReceiveTick == EchoSendTick` | 必须相等 |
| 6 | `ServerTimeTicks - EchoSendTick` | 小且**非负**：官方 12 ticks（=1.2 µs）；`gen3.py` 默认 `--recv-offset-us 0` ⇒ 本项为 **0**，**同样合格**。允许 `0 ≤ d < 1e6` |
| 7 | `SessionKey.AccountServerId` | 等于该会话的账号 id |
| 8 | `SessionKey.MxToken` | 64 字符 base64，与该会话下发的值一致 |
| 9 | wire 字节数 | **不作判据，只记不判。** 实测：我自测（req 325 B）得 **620 B**；真实客户端（req 882 B）得 **600 B**，两者都通过、都进了游戏。原因：响应内层要回显请求里的 `SessionKey`，账号 id 位数 / MxToken 长度一变，明文就变，wire 跟着变。**620 只是"官方那个账号"的数字，不是标准。** |

> 断言 4/5/6 是硬门。**不要用字节数反推结构对错**（`wire = 4·ceil(PKCS7pad(plain,16)+32)/3`，分辨率 16 字节）。

> ### ✅ 已实战验证（2026-11-17 01:24:57）
> 客户端请求 `/api/networktime/sync` → **200 / 600 B**，`gen_kind=networktime-3`，`p3_err=None`，7 键齐备，`ReceiveTick == EchoSendTick`。**随后客户端连续发出 26000 / 90004 / 1005 / 90011 / 8000 / 8006 / 35003 / 16000，并成功进入游戏与新手教程。**
>
> 教训：**字节数不是判据**（自测 620 B、真实客户端 600 B，都对）。真正的判据只有 §2 的 1–8 条，尤其 4/5/6。

---

## 3. 上线步骤与每一步的判据

由 `srv-ops` 执行，**顺序不可换**：

```
# 1) 基线必须仍是它
sha256sum /www/wwwroot/bapatch/tools/account_auth_probe.py
#    期望 368aa5e70941c3f08c59a9ede1b662331e5800dc0a714bc0a30dfbf252dd073a / 90,585 B / 2,212 行

# 2) 只读预演
python3 /tmp/patch_3.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --verify
python3 /tmp/patch_3.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --dry-run
#    判据：基线 sha 命中、锚点全部命中、mtime 未变

# 3) 备份（补丁脚本自己会建，但要确认真的建了）
cp -p /www/wwwroot/bapatch/tools/account_auth_probe.py /www/wwwroot/bapatch/tools/account_auth_probe.py.pre_3.<ts>

# 4) 落盘
python3 /tmp/patch_3.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --apply
python3 -m py_compile /www/wwwroot/bapatch/tools/account_auth_probe.py
#    判据：py_compile 无输出（exit 0）

# 5) 开关（开关就在脚本同目录，见 patch_simple.py:249-253）
echo 1 > /www/wwwroot/bapatch/tools/cn_3.txt

# 6) 重启（pid 2538845 会变）
cd /www/wwwroot/bapatch/tools && setsid nohup python3 account_auth_probe.py \
    >> /www/wwwroot/bapatch/logs/api_probe.out 2>&1 < /dev/null &

# 7) 客户端点一次登录 → 按 §2 清单判
```

**前序补丁的顺序锁**：`patch_3` 必须先落，通过 §2 全部断言后，才允许 apply `patch_8000` / `patch_90004`。原因：那两个补丁的锚点是照着 90,585 B 基线算的，先打会让 `patch_3` 的锚点失配。

---

## 4. 回滚

| 粒度 | 命令 | 生效方式 |
|---|---|---|
| 只关协议 3 | `echo 0 > /www/wwwroot/bapatch/tools/cn_3.txt` | **免重启**（下次请求即生效） |
| 撤销代码 | `cp -p .../account_auth_probe.py.pre_3.<ts> .../account_auth_probe.py` + 重启 | 需重启 |

回滚后应回到：wire 536 B / `gen_kind = min+base`。

---

## 5. 已知的干扰项（判错时先排掉这些）

1. **WAF 会周期性封 `127.0.0.1`**（`/www/server/free_waf/drop_ip.log`）。若客户端报「请确认网络连接状态后重试」，先看这个日志，**不要改 WAF 配置**，让用户手动解封。
2. **`cn_preempt.txt` 绝不能开**。`cn_bridge_exp.txt = decrypt+plain+http200` 时，path A 会把能解密成功的请求代理给 Shittim 直接 return，把 24000/8000/1017/90004 的新分支全拦死。
3. **`account_auth_probe.py` 若被改过，所有锚点全部作废**。每次 apply 前必须重核 sha256。
