# PROGRESS · 协议 3 `api/networktime/sync`（`NetworkTime_Sync`）服务端补丁

> 交付：`work/ba/server/deploy/patch_3.py`（63870 B / sha256 `09584f25fc93777ae795eb2acf6f40e3a2af4cebf9988b3a2506b978ea1f7ef4`）
> 验收脚本：`work/ba/server/deploy/_p3_replay.py`（12541 B / sha256 `65946b813d8d46c1866a4dde8ef0bdb8ee42023cc2c80f10a604538599100556`）
> 全部工作都在本地完成：**没有连服务器 / 没有 ssh/scp / 没有碰线上任何文件**。
> 上线由 Lead 交 srv-ops 执行，命令见 §7。

## 0. TL;DR

| 项 | 值 |
|---|---|
| 问题 | 协议 3 走「通用空构造」，内层没有 `ReceiveTick` / `EchoSendTick`（或为 0） → 客户端算不出时钟偏移 → 后续请求静默停住 |
| 修法 | 把经过官方逐字节验证的 `gen3.build_3()` 语义做成自包含载荷内嵌进 bridge，在三个位置挂 hook 接管；开关 `cn_3.txt` 控制，缺失=关 |
| 效果 | 内层 7 键 / **314 B**，`cn_wire.wrap_response` 后 **恰好 620 B**（= 官方 `resp_bytes`）|
| 红线 | `ReceiveTick == EchoSendTick` 且为**真时间戳**（绝不置 0） |
| 打补丁后 | 90,585 B → **103,900 B**，语法检查 / 自检 / 重放 / 分发证明全绿 |
| 回滚 | `--rollback` 用 `.p3.bak.*` 还原回 90,585 B / `368aa5e7…`（已实测）|

## 1. 事实与证据

### 1.1 线上目标

| 项 | 值 |
|---|---|
| 文件 | `/www/wwwroot/bapatch/tools/account_auth_probe.py` |
| 大小 / sha256 | 90,585 B / `368aa5e70941c3f08c59a9ede1b662331e5800dc0a714bc0a30dfbf252dd073a` |
| 行数 / 端口 / pid | 2,212 行 / 9097 / 2538845 |
| 本地沙箱副本 | `work\ba\server\deploy\_sandbox\p3\account_auth_probe.py`（与线上逐字节相同，sha256 已复核）|

### 1.2 官方抓包（唯一结构基准）

`report/_tmp/official_decoded_201/04_3_api_networktime_sync.response.json`：

```json
{"Protocol":3,"SessionKey":{"AccountServerId":10015354380,"MxToken":"Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA"},"ServerTimeTicks":639304002554622705,"ServerNotification":0,"RequestId":"d1d5579c-9c2b-44e6-a496-c66d4ccca10c","ReceiveTick":639304002554622693,"EchoSendTick":639304002554622693}
```

| 字段 | 值 | 说明 |
|---|---|---|
| `meta.resp_bytes` | **620** | 外层 wire 字节数（本次要精确复现）|
| inner 长度 | **314** | python `json.dumps(..., separators=(",",":"))` |
| `ReceiveTick` / `EchoSendTick` | 639304002554622693 / 639304002554622693 | 两者**相等**（服务端收到请求那一刻）|
| `ServerTimeTicks` | 639304002554622705 | 比两个 tick **大 12 ticks**（1.2 µs，两次取时之差，不是语义差）|
| `RequestId` | `d1d5579c-9c2b-44e6-a496-c66d4ccca10c` | **内层 == 外层 requestid**（同一个 uuid）|
| `SessionKey` | 请求原样回显 | 请求里就带着 `AccountServerId` + 64 字符 `MxToken` |

请求 DTO 侧（`04_3_api_networktime_sync.request.json`）只有 HttpMessage 外壳：
`Protocol` / `Resendable` / `Hash` / `IsTest` / `SessionKey` / `AccountId` / `OSType`，
**没有任何业务字段**，所以服务端没有可回显的客户端 tick —— 两个 tick 都填「收到请求那一刻」
就是官方行为（这一点 `gen3.py --verify-official` 已经逐字节证明过）。

### 1.3 620 B 是怎么来的（容器算式，与 AES 无关）

`cn_wire.wrap_response` 的容器是 `base64( pkcs7(plain) 的密文 + key(32) )`，
密文长度只由 pkcs7 决定（AES-CBC 不改变长度），所以字节数可以手算：

```
inner 314 B  ->  plain 430 B  ->  pkcs7 432 B  + key 32 B = 464 B  ->  base64 = 620 字符
官方抓包实测 resp_bytes = 620
```

反过来验一把线上现状：官方 7 键里去掉 `,"ReceiveTick":639304002554622693` 和
`,"EchoSendTick":639304002554622693`（各 32 B）就是 5 键信封：

```
5 键信封 247 B  ->  plain 359 B  ->  base64 = 536 字符
线上日志里协议 3 的 resp_len = 536
```

**536 与「7 键减去两个 tick」严丝合缝**，所以线上缺的正是那两个 tick ——
与「通用空构造」的现场判断一致（详见 §1.5 的诚实记录）。

### 1.4 tick 口径 = 服务器本地墙钟（不是 UTC）—— 这条必须写死在代码里

`gen_common.simple_ticks()` 的注释说「UTC」，`gen24000.b24000_ticks()` 的注释说「服务器本地墙钟」，
两处结论冲突。用 HAR 元数据可以一锤定音：

```
HAR  entries[143].startedDateTime = 2026-11-15T20:30:55.625Z   ← Unix/UTC 口径
     = 北京时间 2026-11-16 04:30:55.625 (+08)
_timeline.txt 的 Beijing 列      = 04:30:55.625                ← 同一时刻
官方 ServerTimeTicks=639304002554622705 解出来  = 2026-11-16T04:30:55.462      ← 北京墙钟
官方 ReceiveTick=639304002554622693 解出来      = 2026-11-16T04:30:55.462
```

即官方发的是**北京墙钟**，不是 UTC。客户端是北京设备，只有同口径才能算出 ≈0 的偏移；
发 UTC 会整体差 8 小时，所有倒计时/活动时间集体错位。
所以本补丁默认 `mode=local`（`datetime.now()`），并留了 `cn_3_ticks.txt`（写 `utc` 可切换）
作为兜底 —— 万一那台机器的系统时区不是 +08，ops 写一行 `utc` 即可，不用改代码。

### 1.5 诚实记录：线上 536 vs 本地仿真 448

| 场景 | 内层 | wire | 来源 |
|---|---|---|---|
| 线上观测 | 未知（≈250） | **536** | Lead 提供的客户端链路日志 |
| 本地仿真（同一份 90,585 B 文件）| 193（`min+base` 7 个假键）| **448** | `_scratch` 探针实测 |
| 官方 | 314 | **620** | 04_3 抓包 |

为什么本地是 448：这条基线里协议 3 的 `Hash` 能解出来（`12884901893 >> 32 = 3`），
于是落到 `_generic_protocol_response()` 的 `else` 分支，回 `min+base` 的 7 个假键
（`MissionProgressDBs` / `EventMissionProgressDBDict` / …），**没有 SessionKey、没有两个 tick**。
线上 536 的内层尺寸 = 官方 7 键减去两个 tick（见 §1.3），说明线上那一版通用构造
带着 SessionKey/ServerTimeTicks/RequestId 但不带两个 tick —— **两者都是「非官方形状」，
都缺本次要补的东西**。这个差异不影响补丁：三层 hook 都排在所有通用构造之前，
无论线上走的是哪一条（path A / path D / 泛接口），只要开关打开就会被接管。
**上线后请用日志里的 `gen_kind=networktime-3` + `enc_body_len=620` 做最终确认**（见 §7.4）。

## 2. 锚点与插入位置

四个锚点在基线里**各自唯一命中 1 次**（`--verify` 会逐个断言，不唯一直接拒绝动文件）：

| 单元 | 原文件行号 | 锚点文本 | 插入方向 | 位置说明 |
|---|---|---|---|---|
| `PAYLOAD` | 2206 | `if __name__ == '__main__':` | 之前 | bridge 顶层，`if __name__ == '__main__':` 之前 |
| `HOOK-E` | 1677 | `name = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(proto` | 之后 | _bridge() 里协议名解析完、`if exp == 'experror':` 之前 |
| `HOOK-D` | 1827 | `if proto_int: ⏎     obj = cn_nick.build_min_response(proto` | 之前 | _bridge() 的 path D，`if proto_int:` 之前 |
| `HOOK-G` | 1353 | `if num == 90004:` | 之前 | _generic_protocol_response() 里，`if num == 90004:` 之前 |

`--dry-run` 打印的实际插入动作（原文件行号 + 行数）：

```
PAYLOAD: 在原文件第 2206 行之前插入 296 行（锚点 "if __name__ == '__main__':"）
HOOK-E: 在原文件第 1677 行之后插入 15 行（锚点 'name = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(pro'）
HOOK-D: 在原文件第 1827 行之前插入 12 行（锚点 'if proto_int:'）
HOOK-G: 在原文件第 1353 行之前插入 11 行（锚点 'if num == 90004:'）
```

### 2.1 为什么是三层 hook

| hook | 位置 | 拦的是哪条路 | 什么时候会轮到它 |
|---|---|---|---|
| `HOOK-E` | `_bridge()` 里协议名解析完、`if exp == 'experror':` 之前 | **所有**可能的分支（path A 解密+、path B/C、path D、泛接口）| 名字表里能解析出 `NetworkTime_Sync` 时的**正常**情况（bridge 启动时 `load_names()` 就填好了）|
| `HOOK-D` | path D 的 `if proto_int:` 之前 | `cn_nick.build_min_response()` 的 `{"Protocol":3}` 单键回包（192 B）| `rec['req_Hash']` 已被前一条路填上时的安全网 |
| `HOOK-G` | `_generic_protocol_response()` 里 `if num == 90004:` 之前 | `min+base` 7 个假键的泛接口兜底（本地实测 448 B）| 名字解析不到、靠 `Hash>>32` 认出 3 时 |

三层都包在 `try/except` 里，**任何异常只写 `rec['p3_err']` 然后原路返回**，
既不 500 也不断连 —— 客户端断线比返回错数据更难查。
`--prove-dispatch` 会逐层证明「真的会被走到」（把上层 hook 摘掉再跑下层）。

> 与 `patch_simple.py` 的关系：`BAPATCH-P3-*` 与 `BAPATCH-SIMPLE-*` 标记互不重叠，
> 三个既有补丁块（SIMPLE-HOOK-G / SIMPLE-HOOK-D / SIMPLE-PAYLOAD）在 `--verify` 里逐条复核「仍在、未被动过」。
> 完全不碰 `cn_preempt` / `cn_bridge_exp` / `cn_bridge_mode` / 1017 / 24000 / 8000 / 90004。
> 注：这份 90,585 B 基线里**根本没有** `cn_preempt` 相关代码（`patch_preempt.py` 未应用），所以也不存在误拦风险。

### 2.2 运行时开关

| 文件 | 内容 | 语义 |
|---|---|---|
| `/www/wwwroot/bapatch/cn_3.txt` | `1` / `0` | 1=接管协议 3；0 或**文件缺失**=完全回到打补丁前（fail-safe）|
| `/www/wwwroot/bapatch/cn_3_ticks.txt`（可选）| `local`（默认）/ `utc` | tick 口径；缺失=local |

查找顺序：bridge 所在目录 → `/www/wwwroot/bapatch/tools` → `/www/wwwroot/bapatch`。
（线上 bridge 在 `tools/`，但开关按 Lead 要求放 `bapatch/` 根，两者都在查找链里。）

## 3. 插入的代码全文

三个 hook + 内嵌载荷的表头摘要：

```
PAYLOAD  296 行   # >>> BAPATCH-P3-PAYLOAD v1 BEGIN >>> (deploy/patch_3.py 内嵌 P3_PAYLOAD_SRC，sha256=ee55b4cd2c9bd01eda
HOOK-E    15 行           # >>> BAPATCH-P3-HOOK-E v1 BEGIN >>>
HOOK-D    12 行           # >>> BAPATCH-P3-HOOK-D v1 BEGIN >>>
HOOK-G    11 行           # >>> BAPATCH-P3-HOOK-G v1 BEGIN >>>
```

### 3.1 `HOOK-E`（最早接管，按协议名）

```python
        # >>> BAPATCH-P3-HOOK-E v1 BEGIN >>>
        # protocol 3 (NetworkTime_Sync)：在 exp / path A 之前按协议名最早接管，
        # 保证 ReceiveTick / EchoSendTick 一定是真时间戳（红线：不能是通用空构造里的 0）。
        # 先 p3_name_hit（一次字符串比较）挡住别的协议，命中才读开关文件。
        # 开关关 / 生成器异常 -> 原路返回，后面的 path D / generic 兜底完全不变。
        try:
            if p3_name_hit(name) and p3_wants(3):
                _p3e = p3_route(rec, name, 3,
                                self._cn_decode_any(packet_b64, proto_str),
                                cn_wire.wrap_response, hook='HOOK-E')
                if _p3e is not None:
                    return _p3e
        except Exception as _p3e_err:
            rec['p3_err'] = 'HOOK-E ' + repr(_p3e_err)
        # <<< BAPATCH-P3-HOOK-E v1 END <<<
```

### 3.2 `HOOK-D`（path D 安全网）

```python
        # >>> BAPATCH-P3-HOOK-D v1 BEGIN >>>
        # protocol 3：path D 会把它回成 {"Protocol":3} 单键（无 tick），先在这里接管。
        try:
            if p3_wants(proto_int):
                _p3d = p3_route(rec, name, proto_int,
                                self._cn_decode_any(packet_b64, proto_str),
                                cn_wire.wrap_response, hook='HOOK-D')
                if _p3d is not None:
                    return _p3d
        except Exception as _p3d_err:
            rec['p3_err'] = 'HOOK-D ' + repr(_p3d_err)
        # <<< BAPATCH-P3-HOOK-D v1 END <<<
```

### 3.3 `HOOK-G`（泛接口兜底）

```python
        # >>> BAPATCH-P3-HOOK-G v1 BEGIN >>>
        # protocol 3：泛接口兜底（min+base 假键）之前接管，回官方 7 键 / 620 B。
        # frag 用 locals().get()：万一别的版本里这个局部变量改名也不至于 NameError。
        try:
            _p3g = p3_route(rec, name, num, locals().get('frag'),
                            cn_wire.wrap_response, hook='HOOK-G')
            if _p3g is not None:
                return _p3g
        except Exception as _p3g_err:
            rec['p3_err'] = 'HOOK-G ' + repr(_p3g_err)
        # <<< BAPATCH-P3-HOOK-G v1 END <<<
```

### 3.4 `PAYLOAD`（内嵌载荷生成器，唯一真源）

这段是**原样内嵌**进 bridge 顶层（`if __name__ == '__main__':` 之前）的完整模块，
`--verify` 会断言「bridge 里的副本 == `patch_3.py` 里的 `P3_PAYLOAD_SRC`」逐字节相等，
并拿 `gen3.build_3()` 跑 5 组输入逐字节对比。全文：

```python
# -*- coding: utf-8 -*-
"""NetworkTime_Sync (protocol 3) 载荷生成器 —— 内嵌进 bridge 的运行时真源。

与 deploy/gen3.py 的 build_3() 逐字节等价（patch_3.py --verify 用真生成器比对）：
    acct = Account(server_id, mxtoken, request_id, now)      # now 必须是 datetime
    obj  = build_3(acct)                                     # ReceiveTick == EchoSendTick
    顶层键序 = official_spec.json protocols["3"].top_key_order

官方 04_3 抓包（report/_tmp/official_decoded_201/04_3_api_networktime_sync.response.json）：
    inner 314 B / wire 620 B，7 键；
    ReceiveTick == EchoSendTick == 639304002554622693；
    ServerTimeTicks = ...705（比前两者大 12 ticks = 1.2 µs，同一次取时的抖动）；
    inner.RequestId == outer.requestid（同一个 uuid）。
请求 DTO 没有业务字段（只有 HttpMessage 外壳），所以服务端**没有**可回显的客户端 tick，
两个 tick 都填「收到请求那一刻」就是官方行为。

tick 口径 = 服务器本地墙钟（不是 UTC）：
    官方 ServerTimeTicks=639304002554622705 解出来是 2026-11-16T04:30:55.462，
    HAR 里同一条请求的 startedDateTime=2026-11-15T20:30:55.625Z（Unix 口径），
    _timeline.txt 的 Beijing 列写 04:30:55.625 —— 即官方发的是北京墙钟。
    客户端是北京设备，只有同口径才能算出 ≈0 的偏移；发 UTC 会整体差 8 小时。
    需要时可用 cn_3_ticks.txt 写 'utc' 覆盖。

约定（原样贴进 bridge 的模块命名空间，所以）：
  * 不写 from __future__ / 不写 if __name__ == '__main__'；
  * 只用标准库，且全部用 _p3* 别名 import，不污染 bridge 现有全局名；
  * import 期不碰文件系统、不碰网络。
"""
import base64 as _p3base64
import datetime as _p3dt
import hashlib as _p3hashlib
import os as _p3os
import re as _p3re
import uuid as _p3uuid

P3_PROTOCOL = 3
P3_NAME = 'NetworkTime_Sync'

# official_spec.json -> protocols["3"].top_key_order
# （patch_3.py --verify 会重新读 spec 并断言这张表没过期）
P3_ORDER = ('Protocol', 'SessionKey', 'ServerTimeTicks', 'ServerNotification',
            'RequestId', 'ReceiveTick', 'EchoSendTick')

P3_SWITCH_FILE = 'cn_3.txt'
P3_TICKS_FILE = 'cn_3_ticks.txt'
# 开关查找顺序：bridge 所在目录 -> 线上 tools/ -> 线上 bapatch/
P3_FALLBACK_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')
P3_DEFAULT_ACCOUNT = 10015354380
P3_EPOCH = _p3dt.datetime(1, 1, 1)


# ---------------------------------------------------------------- 开关 / 小工具
def p3_dirs():
    """开关文件的候选目录（有序）。"""
    out = []
    try:
        out.append(_p3os.path.dirname(_p3os.path.abspath(__file__)))
    except Exception:
        pass
    for d in P3_FALLBACK_DIRS:
        if d not in out:
            out.append(d)
    return out


def p3_read_file(fn, base=None):
    """读一个小开关文件 -> (路径, 内容)。找不到 -> (None, None)。"""
    dirs = ([base] if base else []) + p3_dirs()
    for d in dirs:
        if not d:
            continue
        p = _p3os.path.join(d, fn)
        try:
            with open(p, 'r') as fh:
                return p, fh.read().strip()
        except Exception:
            continue
    return None, None


def p3_switch_on(base=None):
    """协议 3 是否启用。缺失 / 读不到 / 内容不是真值 -> False（fail-safe）。"""
    _p, v = p3_read_file(P3_SWITCH_FILE, base)
    if v is None:
        return False
    return v.strip().lower() in ('1', 'on', 'true', 'yes')


def p3_wants(num, base=None):
    """协议号是 3 且开关打开 —— 给 bridge 的分发处做前置判断（不解密、不构包）。"""
    try:
        n = int(num)
    except Exception:
        return False
    return n == P3_PROTOCOL and p3_switch_on(base)


def p3_num(num=None, name=None):
    """协议号判定：Hash>>32 命中 3，或者外层 protocol 就是 NetworkTime_Sync。"""
    try:
        n = int(num)
    except Exception:
        n = None
    if n == P3_PROTOCOL:
        return P3_PROTOCOL
    if isinstance(name, str) and name == P3_NAME:
        return P3_PROTOCOL
    return None


def p3_name_hit(name):
    """廉价预判（不碰文件系统）：外层协议名就是 NetworkTime_Sync？

    HOOK-E 在**每个**请求上都会经过，所以先用一次字符串比较挡住其它协议，
    连开关文件都不读；只有命中协议 3 才去碰盘。
    """
    return isinstance(name, str) and name == P3_NAME


def p3_ticks_mode(base=None):
    _p, v = p3_read_file(P3_TICKS_FILE, base)
    if v and v.strip().lower() == 'utc':
        return 'utc'
    return 'local'


def p3_ticks(dt=None, mode='local'):
    """.NET ticks（100ns，自 0001-01-01）。整数运算，不经 float。"""
    if dt is None:
        if str(mode).lower() == 'utc':
            dt = _p3dt.datetime.now(_p3dt.timezone.utc).replace(tzinfo=None)
        else:
            dt = _p3dt.datetime.now()
    elif getattr(dt, 'tzinfo', None) is not None:
        if str(mode).lower() == 'utc':
            dt = dt.astimezone(_p3dt.timezone.utc).replace(tzinfo=None)
        else:
            dt = dt.astimezone().replace(tzinfo=None)
    delta = dt - P3_EPOCH
    return (delta.days * 86400 + delta.seconds) * 10000000 + delta.microseconds * 10


def p3_now(mode='local'):
    if str(mode).lower() == 'utc':
        return _p3dt.datetime.now(_p3dt.timezone.utc).replace(tzinfo=None)
    return _p3dt.datetime.now()


# ---------------------------------------------------------------- 账号 / 令牌
def p3_session_from_frag(frag):
    """从客户端请求片段里取 SessionKey（官方就是原样回显它）。"""
    sid = mx = None
    if isinstance(frag, str) and frag:
        m = _p3re.search(r'"AccountServerId"\s*:\s*(\d+)', frag)
        if m:
            sid = int(m.group(1))
        m = _p3re.search(r'"MxToken"\s*:\s*"([^"]{8,200})"', frag)
        if m:
            mx = m.group(1)
    return sid, mx


def p3_account_id(rec=None, frag=None):
    sid, _mx = p3_session_from_frag(frag)
    if sid:
        return int(sid)
    try:
        sess = globals().get('SESSION')
        sk = getattr(sess, 'session_key', None) or {}
        if isinstance(sk, dict) and sk.get('AccountServerId'):
            return int(sk['AccountServerId'])
        aid = getattr(sess, 'account_id', None)
        if aid:
            return int(aid)
    except Exception:
        pass
    if isinstance(rec, dict):
        for k in ('acct_server_id', 'req_AccountServerId'):
            v = rec.get(k)
            if v:
                try:
                    return int(v)
                except Exception:
                    pass
    return P3_DEFAULT_ACCOUNT


def p3_mxtoken(account_id):
    """由账号派生 64 字符 base64 MxToken（sha384 48 字节，与 gen_common.Account 同一公式）。"""
    raw = _p3hashlib.sha384(
        ('ba-private-server:%d' % int(account_id)).encode('utf-8')).digest()
    return _p3base64.b64encode(raw).decode('ascii')


def p3_requestid(rec=None):
    """外层 requestid / 内层 RequestId 用同一个值（官方逐字节相同）。"""
    rid = None
    fn = globals().get('pick_requestid')
    if callable(fn):
        try:
            rid = fn(rec if isinstance(rec, dict) else {})
        except Exception:
            rid = None
    if not rid:
        rid = str(_p3uuid.uuid4())
    return rid


# ---------------------------------------------------------------- 载荷
def p3_build(account_id, mxtoken, request_id, ticks, server_ticks=None):
    """7 键官方结构。

    ReceiveTick == EchoSendTick == ticks  —— 红线：绝不能是 0（客户端靠它算时钟偏移）。
    ServerTimeTicks = server_ticks（不给就同 ticks）。官方 ServerTimeTicks 比两个 tick 大
    12 ticks（1.2 µs）：那是「收到请求」和「组包发出」两次取时之差，运行时按两次采样给。
    """
    ticks = int(ticks)
    stt = ticks if server_ticks is None else int(server_ticks)
    if stt < ticks:
        stt = ticks
    obj = {
        'Protocol': P3_PROTOCOL,
        'SessionKey': {'AccountServerId': int(account_id), 'MxToken': mxtoken},
        'ServerTimeTicks': stt,
        'ServerNotification': 0,
        'RequestId': request_id,
        'ReceiveTick': ticks,
        'EchoSendTick': ticks,
    }
    return dict((k, obj[k]) for k in P3_ORDER if k in obj)


def p3_inner_len(obj):
    return len(json_dumps_compact(obj))


def json_dumps_compact(obj):
    import json as _j
    return _j.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def p3_route(rec, name=None, num=None, frag=None, send=None, base=None, hook=None):
    """协议 3 的接管线。返回 (200, wire, ctype)；不管 -> None（交回原有兜底）。

    send 必须注入（bridge 传 cn_wire.wrap_response，测试可传替身）：
        send(protocol_name, inner_obj, requestid) -> (wire, plain, key)
    任何异常都往上抛，由 hook 的 try/except 兜住并记 rec['p3_err']。
    """
    proto = p3_num(num, name)
    if proto is None:
        return None
    if not p3_switch_on(base):
        if isinstance(rec, dict):
            rec['p3_off'] = proto
        return None
    if send is None:
        return None

    if isinstance(rec, dict) and isinstance(frag, str) and frag:
        rec['p3_frag_head'] = frag[:200]

    sid_frag, mx_frag = p3_session_from_frag(frag)
    account_id = p3_account_id(rec, frag)
    mxtoken = mx_frag or p3_mxtoken(account_id)
    mode = p3_ticks_mode(base)
    ticks = p3_ticks(p3_now(mode), mode)                 # 收到请求那一刻 -> 两个 tick
    server_ticks = p3_ticks(p3_now(mode), mode)          # 组包那一刻 -> ServerTimeTicks
    rid = p3_requestid(rec)

    obj = p3_build(account_id, mxtoken, rid, ticks, server_ticks=server_ticks)
    wire, plain, key = send(P3_NAME, obj, rid)

    if isinstance(rec, dict):
        rec['gen_kind'] = 'networktime-3'
        rec['p3_hook'] = hook or '?'
        rec['p3_proto'] = proto
        rec['p3_name'] = P3_NAME
        rec['p3_account_id'] = account_id
        rec['p3_session_from_request'] = bool(sid_frag or mx_frag)
        rec['p3_ticks_mode'] = mode
        rec['p3_ticks'] = int(ticks)
        rec['p3_server_ticks'] = obj['ServerTimeTicks']
        rec['p3_server_tick_delta'] = obj['ServerTimeTicks'] - obj['ReceiveTick']
        rec['p3_receive_tick'] = obj['ReceiveTick']
        rec['p3_echo_tick'] = obj['EchoSendTick']
        rec['p3_tick_delta'] = obj['EchoSendTick'] - obj['ReceiveTick']
        rec['p3_requestid_echo'] = (obj.get('RequestId') == rid)
        rec['p3_keys'] = len(obj)
        rec['enc_requestid'] = rid
        rec['enc_inner_keys'] = len(obj)
        rec['enc_plain_len'] = len(plain)
        rec['enc_body_len'] = len(wire)
        rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
    return 200, wire, 'text/plain; charset=utf-8'
```

## 4. 六步验证：命令 + 真实输出

Python：`C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`（3.12.14）。
所有 `--src` 都显式传给沙箱副本 `work\ba\server\deploy\_sandbox\p3\account_auth_probe.py`。

> 本机没有 `cryptography`（真机有），所以仿真里的 `cn_wire` 换成**等长替身**：
> 密文长度只由 pkcs7 决定、AES-CBC 不改变长度，`len(wire)` 与真机逐字节等长；
> plaintext 原样回传供断言，因此**不依赖 AES 实现也能证明 620 B 与内层 tick**。
> 注意：`--verify` / `--prove-dispatch` / `_p3_replay.py` 三者在任何机器上都用替身（故意的，
> 免得被加密细节干扰）；真 `cn_wire.wrap_response` 的调用点与 bridge 现有 `_cn_send_envelope`
> 与 1017 分支**完全同一签名**（`wrap_response(name, obj, rid)` 三参数），没有引入新用法。

### 步骤 1 `--verify`（基线 sha256 + 锚点命中，不写文件）

```powershell
& C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe "C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\patch_3.py" --src "C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py" --verify
```
```
src     : C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py
          90585 字节 / 2212 行 / sha256 368aa5e70941c3f08c59a9ede1b662331e5800dc0a714bc0a30dfbf252dd073a
patched : 否
  INFO  src = C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py  (90585 字节 / 2212 行 / sha256 368aa5e70941c3f0)
  INFO  状态 = 未打补丁（校验基线+锚点）
  PASS  python 语法检查 compile() 
  PASS  基线大小 == 90585（实测 90585）
  PASS  基线 sha256 == 368aa5e70941c3f0（实测 368aa5e70941c3f0）
  PASS  锚点 HOOK-E 唯一命中 1 次（第 1677 行，_bridge() 里协议名解析完、`if exp == 'experror':` 之前）
  PASS  锚点 HOOK-D 唯一命中 1 次（第 1827 行，_bridge() 的 path D，`if proto_int:` 之前）
  PASS  锚点 HOOK-G 唯一命中 1 次（第 1353 行，_generic_protocol_response() 里，`if num == 90004:` 之前）
  PASS  锚点 PAYLOAD 唯一命中 1 次（第 2206 行，bridge 顶层，`if __name__ == '__main__':` 之前）
  PASS  基线里没有 BAPATCH-P3 残留标记
  INFO  未打补丁，跳过 P3_ORDER 比对（spec 键序 = ['Protocol', 'SessionKey', 'ServerTimeTicks', 'ServerNotification', 'RequestId', 'ReceiveTick', 'EchoSendTick']）
结论: PASS
```

### 步骤 2 `--dry-run`（打印插入位置与代码，不写文件）

```
src     : C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py
          90585 字节 / 2212 行 / sha256 368aa5e70941c3f08c59a9ede1b662331e5800dc0a714bc0a30dfbf252dd073a
patched : 否

== 插入动作 ==
  PAYLOAD: 在原文件第 2206 行之前插入 296 行（锚点 "if __name__ == '__main__':"）
  HOOK-E: 在原文件第 1677 行之后插入 15 行（锚点 'name = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(pro'）
  HOOK-D: 在原文件第 1827 行之前插入 12 行（锚点 'if proto_int:'）
  HOOK-G: 在原文件第 1353 行之前插入 11 行（锚点 'if num == 90004:'）

== 将要插入的代码 ==
  [PAYLOAD] 插到第 2206 行之前（bridge 顶层，`if __name__ == '__main__':` 之前）
  [HOOK-E] 插到第 1677 行之前（_bridge() 里协议名解析完、`if exp == 'experror':` 之前）
  [HOOK-D] 插到第 1827 行之前（_bridge() 的 path D，`if proto_int:` 之前）
  [HOOK-G] 插到第 1353 行之前（_generic_protocol_response() 里，`if num == 90004:` 之前）

  ---- HOOK-E ----
          # >>> BAPATCH-P3-HOOK-E v1 BEGIN >>>
          # protocol 3 (NetworkTime_Sync)：在 exp / path A 之前按协议名最早接管，
          # 保证 ReceiveTick / EchoSendTick 一定是真时间戳（红线：不能是通用空构造里的 0）。
          # 先 p3_name_hit（一次字符串比较）挡住别的协议，命中才读开关文件。
          # 开关关 / 生成器异常 -> 原路返回，后面的 path D / generic 兜底完全不变。
          try:
              if p3_name_hit(name) and p3_wants(3):
                  _p3e = p3_route(rec, name, 3,
                                  self._cn_decode_any(packet_b64, proto_str),
                                  cn_wire.wrap_response, hook='HOOK-E')
                  if _p3e is not None:
                      return _p3e
          except Exception as _p3e_err:
              rec['p3_err'] = 'HOOK-E ' + repr(_p3e_err)
          # <<< BAPATCH-P3-HOOK-E v1 END <<<

  ---- HOOK-D ----
          # >>> BAPATCH-P3-HOOK-D v1 BEGIN >>>
          # protocol 3：path D 会把它回成 {"Protocol":3} 单键（无 tick），先在这里接管。
          try:
              if p3_wants(proto_int):
                  _p3d = p3_route(rec, name, proto_int,
                                  self._cn_decode_any(packet_b64, proto_str),
                                  cn_wire.wrap_response, hook='HOOK-D')
                  if _p3d is not None:
                      return _p3d
          except Exception as _p3d_err:
              rec['p3_err'] = 'HOOK-D ' + repr(_p3d_err)
          # <<< BAPATCH-P3-HOOK-D v1 END <<<

  ---- HOOK-G ----
          # >>> BAPATCH-P3-HOOK-G v1 BEGIN >>>
          # protocol 3：泛接口兜底（min+base 假键）之前接管，回官方 7 键 / 620 B。
          # frag 用 locals().get()：万一别的版本里这个局部变量改名也不至于 NameError。
          try:
              _p3g = p3_route(rec, name, num, locals().get('frag'),
                              cn_wire.wrap_response, hook='HOOK-G')
              if _p3g is not None:
                  return _p3g
          except Exception as _p3g_err:
              rec['p3_err'] = 'HOOK-G ' + repr(_p3g_err)
          # <<< BAPATCH-P3-HOOK-G v1 END <<<

  ---- PAYLOAD 摘要 ----
  296 行 / sha256 ee55b4cd2c9bd01e
  头: # >>> BAPATCH-P3-PAYLOAD v1 BEGIN >>> (deploy/patch_3.py 内嵌 P3_PAYLOAD_SRC，sha256=ee55b4cd2c9bd01eda252fa15509
  尾: # <<< BAPATCH-P3-PAYLOAD v1 END <<<

== diff（71 行）==
  --- C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py
  +++ C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py.patched
  @@ -1350,6 +1350,17 @@
           except Exception as _sg_err:
               rec['simple_err'] = 'HOOK-G ' + repr(_sg_err)
           # <<< BAPATCH-SIMPLE-HOOK-G v1 END <<<
  +        # >>> BAPATCH-P3-HOOK-G v1 BEGIN >>>
  +        # protocol 3：泛接口兜底（min+base 假键）之前接管，回官方 7 键 / 620 B。
  +        # frag 用 locals().get()：万一别的版本里这个局部变量改名也不至于 NameError。
  +        try:
  +            _p3g = p3_route(rec, name, num, locals().get('frag'),
  +                            cn_wire.wrap_response, hook='HOOK-G')
  +            if _p3g is not None:
  +                return _p3g
  +        except Exception as _p3g_err:
  +            rec['p3_err'] = 'HOOK-G ' + repr(_p3g_err)
  +        # <<< BAPATCH-P3-HOOK-G v1 END <<<
           if num == 90004:
               from datetime import datetime as _d9
               _n9 = _d9.now()
  @@ -1676,6 +1687,21 @@
           rec['exp'] = exp
           name = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(proto_str)
           rec['protocol_name'] = name
  +        # >>> BAPATCH-P3-HOOK-E v1 BEGIN >>>
  +        # protocol 3 (NetworkTime_Sync)：在 exp / path A 之前按协议名最早接管，
  +        # 保证 ReceiveTick / EchoSendTick 一定是真时间戳（红线：不能是通用空构造里的 0）。
  +        # 先 p3_name_hit（一次字符串比较）挡住别的协议，命中才读开关文件。
  +        # 开关关 / 生成器异常 -> 原路返回，后面的 path D / generic 兜底完全不变。
  +        try:
  +            if p3_name_hit(name) and p3_wants(3):
  +                _p3e = p3_route(rec, name, 3,
  +                                self._cn_decode_any(packet_b64, proto_str),
  +                                cn_wire.wrap_response, hook='HOOK-E')
  +                if _p3e is not None:
  +                    return _p3e
  +        except Exception as _p3e_err:
  +            rec['p3_err'] = 'HOOK-E ' + repr(_p3e_err)
  +        # <<< BAPATCH-P3-HOOK-E v1 END <<<
   
           if exp == 'experror':
               env = json.dumps({"protocol": "Error",
  @@ -1824,6 +1850,18 @@
           except Exception as _sg_err:
               rec['simple_err'] = 'HOOK-D ' + repr(_sg_err)
           # <<< BAPATCH-SIMPLE-HOOK-D v1 END <<<
  +        # >>> BAPATCH-P3-HOOK-D v1 BEGIN >>>
  +        # protocol 3：path D 会把它回成 {"Protocol":3} 单键（无 tick），先在这里接管。
  +        try:
  +            if p3_wants(proto_int):
  +                _p3d = p3_route(rec, name, proto_int,
  +                                self._cn_decode_any(packet_b64, proto_str),
  +                                cn_wire.wrap_response, hook='HOOK-D')
  +                if _p3d is not None:
  +                    return _p3d
  +        except Exception as _p3d_err:
  +            rec['p3_err'] = 'HOOK-D ' + repr(_p3d_err)
  +        # <<< BAPATCH-P3-HOOK-D v1 END <<<
           if proto_int:
               obj = cn_nick.build_min_response(proto_int)
               rec['fallback'] = 'min-envelope'
  @@ -2203,6 +2241,9 @@
           rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
       return 200, wire, 'text/plain; charset=utf-8'
   # <<< BAPATCH-SIMPLE-PAYLOAD v1 END <<<
  +# >>> BAPATCH-P3-PAYLOAD v1 BEGIN >>> (deploy/patch_3.py 内嵌 P3_PAYLOAD_SRC，sha256=ee55b4cd2c9bd01eda252fa1550935e3e2637a12600759a4ff9652045d60789a) >>>
  +# ...[294 行载荷生成器原样内嵌自 patch_3.py 的 P3_PAYLOAD_SRC，--full-diff 查看]...
  +# <<< BAPATCH-P3-PAYLOAD v1 END <<<
   if __name__ == '__main__':
       n = load_names()
       print('protocol name table =', n, 'entries')

语法检查: PASS
--dry-run：没有写文件。mtime/size 未变: True（(1794849619256981400, 90585)）
           开关文件也没动（正式执行时 --switches keep -> C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\cn_3.txt）
mtime_unchanged=True  size=90585  mtimeUtc=2026-11-16T17:20:19.2569814Z
```
mtime 复核（脚本外的独立取证，接在 dry-run 之后）：

```powershell
$src = "C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py"
$b = (Get-Item $src).LastWriteTimeUtc.Ticks
& C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe "C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\patch_3.py" --src $src --dry-run
$a = (Get-Item $src).LastWriteTimeUtc.Ticks
"mtime_unchanged=$($b -eq $a)  size=$((Get-Item $src).Length)"
```
```
mtime_unchanged=True  size=90585  mtimeUtc=2026-11-16T17:20:19.2569814Z
```

### 步骤 3 `--apply`（先备份再写，写完立即自检）

```
src     : C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py
          90585 字节 / 2212 行 / sha256 368aa5e70941c3f08c59a9ede1b662331e5800dc0a714bc0a30dfbf252dd073a
patched : 否

== 插入动作 ==
  PAYLOAD: 在原文件第 2206 行之前插入 296 行（锚点 "if __name__ == '__main__':"）
  HOOK-E: 在原文件第 1677 行之后插入 15 行（锚点 'name = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(pro'）
  HOOK-D: 在原文件第 1827 行之前插入 12 行（锚点 'if proto_int:'）
  HOOK-G: 在原文件第 1353 行之前插入 11 行（锚点 'if num == 90004:'）

== diff（71 行）==
  --- C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py
  +++ C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py.patched
  @@ -1350,6 +1350,17 @@
           except Exception as _sg_err:
               rec['simple_err'] = 'HOOK-G ' + repr(_sg_err)
           # <<< BAPATCH-SIMPLE-HOOK-G v1 END <<<
  +        # >>> BAPATCH-P3-HOOK-G v1 BEGIN >>>
  +        # protocol 3：泛接口兜底（min+base 假键）之前接管，回官方 7 键 / 620 B。
  +        # frag 用 locals().get()：万一别的版本里这个局部变量改名也不至于 NameError。
  +        try:
  +            _p3g = p3_route(rec, name, num, locals().get('frag'),
  +                            cn_wire.wrap_response, hook='HOOK-G')
  +            if _p3g is not None:
  +                return _p3g
  +        except Exception as _p3g_err:
  +            rec['p3_err'] = 'HOOK-G ' + repr(_p3g_err)
  +        # <<< BAPATCH-P3-HOOK-G v1 END <<<
           if num == 90004:
               from datetime import datetime as _d9
               _n9 = _d9.now()
  @@ -1676,6 +1687,21 @@
           rec['exp'] = exp
           name = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(proto_str)
           rec['protocol_name'] = name
  +        # >>> BAPATCH-P3-HOOK-E v1 BEGIN >>>
  +        # protocol 3 (NetworkTime_Sync)：在 exp / path A 之前按协议名最早接管，
  +        # 保证 ReceiveTick / EchoSendTick 一定是真时间戳（红线：不能是通用空构造里的 0）。
  +        # 先 p3_name_hit（一次字符串比较）挡住别的协议，命中才读开关文件。
  +        # 开关关 / 生成器异常 -> 原路返回，后面的 path D / generic 兜底完全不变。
  +        try:
  +            if p3_name_hit(name) and p3_wants(3):
  +                _p3e = p3_route(rec, name, 3,
  +                                self._cn_decode_any(packet_b64, proto_str),
  +                                cn_wire.wrap_response, hook='HOOK-E')
  +                if _p3e is not None:
  +                    return _p3e
  +        except Exception as _p3e_err:
  +            rec['p3_err'] = 'HOOK-E ' + repr(_p3e_err)
  +        # <<< BAPATCH-P3-HOOK-E v1 END <<<
   
           if exp == 'experror':
               env = json.dumps({"protocol": "Error",
  @@ -1824,6 +1850,18 @@
           except Exception as _sg_err:
               rec['simple_err'] = 'HOOK-D ' + repr(_sg_err)
           # <<< BAPATCH-SIMPLE-HOOK-D v1 END <<<
  +        # >>> BAPATCH-P3-HOOK-D v1 BEGIN >>>
  +        # protocol 3：path D 会把它回成 {"Protocol":3} 单键（无 tick），先在这里接管。
  +        try:
  +            if p3_wants(proto_int):
  +                _p3d = p3_route(rec, name, proto_int,
  +                                self._cn_decode_any(packet_b64, proto_str),
  +                                cn_wire.wrap_response, hook='HOOK-D')
  +                if _p3d is not None:
  +                    return _p3d
  +        except Exception as _p3d_err:
  +            rec['p3_err'] = 'HOOK-D ' + repr(_p3d_err)
  +        # <<< BAPATCH-P3-HOOK-D v1 END <<<
           if proto_int:
               obj = cn_nick.build_min_response(proto_int)
               rec['fallback'] = 'min-envelope'
  @@ -2203,6 +2241,9 @@
           rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
       return 200, wire, 'text/plain; charset=utf-8'
   # <<< BAPATCH-SIMPLE-PAYLOAD v1 END <<<
  +# >>> BAPATCH-P3-PAYLOAD v1 BEGIN >>> (deploy/patch_3.py 内嵌 P3_PAYLOAD_SRC，sha256=ee55b4cd2c9bd01eda252fa1550935e3e2637a12600759a4ff9652045d60789a) >>>
  +# ...[294 行载荷生成器原样内嵌自 patch_3.py 的 P3_PAYLOAD_SRC，--full-diff 查看]...
  +# <<< BAPATCH-P3-PAYLOAD v1 END <<<
   if __name__ == '__main__':
       n = load_names()
       print('protocol name table =', n, 'entries')

语法检查: PASS

已写入。备份: C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py.p3.bak.20261117-011931
  写入后 103900 字节 / sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8
  还原命令: cp -a C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py.p3.bak.20261117-011931 C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py
  （或 python patch_3.py --src C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py --rollback）
开关: C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\cn_3.txt=1（保留文件）

== 打完补丁后的自检 ==
  INFO  src = C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py  (103900 字节 / 2546 行 / sha256 563c1942289968e3)
  INFO  状态 = 已打补丁（校验补丁后不变量）
  PASS  python 语法检查 compile() 
  PASS  PAYLOAD 标记成对、各 1 处（BEGIN 1 / END 1）
  PASS  HOOK-E 标记成对、各 1 处（BEGIN 1 / END 1）
  PASS  HOOK-D 标记成对、各 1 处（BEGIN 1 / END 1）
  PASS  HOOK-G 标记成对、各 1 处（BEGIN 1 / END 1）
  PASS  内嵌 PAYLOAD 逐字节 == patch_3.py 的 P3_PAYLOAD_SRC（sha256 ee55b4cd2c9bd01e / ee55b4cd2c9bd01e）
  PASS  PAYLOAD 标记里记的 sha256 与真源一致（ee55b4cd2c9bd01e）
  PASS  HOOK-E 代码块逐字节 == patch_3.py 里生成的那份
  PASS  HOOK-D 代码块逐字节 == patch_3.py 里生成的那份
  PASS  HOOK-G 代码块逐字节 == patch_3.py 里生成的那份
  PASS  HOOK-G 落在 _generic_protocol_response() 内（def@48420 < hook@49790 < 下一函数@54418）
  PASS  HOOK-G 在 `if num == 90004:` 之前（hook@49790 < anchor@50293）
  PASS  HOOK-D 在 path D 的 `if proto_int:` 之前（hook@74973 < anchor@75532）
  PASS  HOOK-E 在协议名解析之后、exp 分支之前（name@66920 < hook@66964 < exp@67703）
  PASS  PAYLOAD 在 `if __name__ == '__main__':` 之前（payload@87984 < anchor@97777）
  PASS  既有补丁 BAPATCH-SIMPLE-HOOK-G 仍在（未被动过）
  PASS  既有补丁 BAPATCH-SIMPLE-HOOK-D 仍在（未被动过）
  PASS  既有补丁 BAPATCH-SIMPLE-PAYLOAD 仍在（未被动过）
  PASS  内嵌载荷可 exec
  PASS  开关文件缺失 -> 判定「关」（fail-safe）
  PASS  cn_3.txt=1 -> 协议 3「开」
  PASS  开关打开也不会接管别的协议（4000 / 1017 -> False）
  PASS  p3_wants(None) -> False（不会 TypeError）
  PASS  p3_name_hit 只认 NetworkTime_Sync（HOOK-E 每个请求都过，必须先挡一下）
  PASS  cn_3.txt=0 -> 「关」
  PASS  内层键序 == P3_ORDER（7 键）
  PASS  ReceiveTick == EchoSendTick == 639304002554622693（红线：非 0 且相等）
  PASS  ServerTimeTicks 缺省 == 两个 tick（同一时刻只采一次时不自相矛盾）
  PASS  内层 RequestId 用注入值（== 外层 requestid）
  PASS  ServerTimeTicks 可单独给（+12 ticks，复现官方两次取时）且不动两个 tick
  PASS  从请求片段取到 SessionKey（AccountServerId / MxToken 各 10015354380 / 64 字符）
  PASS  无请求 SessionKey 时 MxToken 由账号派生（64 字符 base64，可复现）
  PASS  用官方 SessionKey/tick 重建内层 == 官方 inner（逐字节，314 B）
  PASS  官方 inner 的 ReceiveTick == EchoSendTick（639304002554622693）
  PASS  官方 ServerTimeTicks 比两个 tick 大 12 ticks
  PASS  cn_wire 容器长度 == 620（官方 resp_bytes=620，plain 430 B）
  PASS  抓包原文 resp_bytes == 620（对照值）
  PASS  外层 protocol == 'NetworkTime_Sync'
  PASS  内嵌生成器 == 真生成器 gen3.build_3()（5 组输入逐字节相同）
  PASS  gen3.build_3 用官方输入回灌 == 官方 inner（--verify-official 口径）
  PASS  内嵌生成器 == gen3.build_3（官方输入，含独立 ServerTimeTicks）
  INFO  gen3.build_3 内层 314 B（官方 314 B）
  PASS  P3_ORDER == official_spec.json protocols["3"].top_key_order (['Protocol', 'SessionKey', 'ServerTimeTicks', 'ServerNotification', 'RequestId', 'ReceiveTick', 'EchoSendTick'])
自检: 全绿
```

### 步骤 4 `py_compile`（语法）

```
py_compile OK  size=103900  sha256=563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8
```

### 步骤 5a 本地 replay（`_p3_replay.py`，22 项断言）

```powershell
& C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe "C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_p3_replay.py" --target "C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py"
```
```
target : C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py
         103900 字节 / sha256 563c1942289968e3
patched: 是

== 重放断言 ==
  INFO  A0   响应体 = base64(密文+key)（620 B），外层明文 430 B
  PASS  A1   外层 protocol == 'NetworkTime_Sync'（实测 'NetworkTime_Sync'）
  PASS  A1   HTTP 200 / Content-Type 'text/plain; charset=utf-8'（官方同款 text/plain）
  PASS  A2   wire 字节数 == 620（实测 620）
  PASS  A2   base64(密文+key32) 形态成立：raw 464 B = ct 432 B + key 32 B
  PASS  A3   内层键序 == 官方 top_key_order（7 键）
  PASS  A3   内层键序 == official_spec.json protocols["3"].top_key_order
  PASS  A4   ReceiveTick 是真时间戳（639304751854913200，非 0）
  PASS  A4   ReceiveTick == EchoSendTick（红线）：639304751854913200 == 639304751854913200
  PASS  A5   ServerTimeTicks - ReceiveTick = 0 ticks（0..100000 即 0..10 ms）
  PASS  A6   内层 RequestId == 外层 requestid 且是 uuid 形态（4c7509e0）
  PASS  A7   ReceiveTick 解回 2026-11-17 01:19:45.491320，与现在 2026-11-17 01:19:45 差 0.0 s（<180 s）
  PASS  A8   请求 SessionKey 原样回显（AccountServerId=10015354380 / MxToken 64 字符）
  PASS  A8   rec.gen_kind='networktime-3' / p3_hook='HOOK-E' / ticks_mode='local'
  PASS  A9   生成器抛异常 -> 200 / 448 B（== 打补丁前 448 B），没有 500/断连
  PASS  A9   异常留痕 rec.p3_err="HOOK-G RuntimeError('replay-injected failure')"
  PASS  A10  cn_3.txt 缺失 -> 200 / 448 B == 打补丁前（行为完全回退）
  PASS  A10  cn_3.txt=0 -> 200 / 448 B == 打补丁前
  PASS  A11  p3_route 对别的协议返回 None（'4000/1017/24000/8000/90004/1005/26000 全部 None'）
  PASS  A12  连发 5 次长度 [620, 620, 620, 620, 620]（恒为 620）
  PASS  A13  packet 解不出来时仍回 200 / 620 B（不 500、不断连）
  PASS  A13  兜底 SessionKey 由账号派生（MxToken 64 字符）且两个 tick 仍是真值
  PASS  REF  官方明文 430 B -> pkcs7 432 + key 32 -> base64 = 620（容器算式自证）

22 项断言 / 0 FAIL / ALL PASS
```

### 步骤 5b `--prove-dispatch`（证明新分支真的被走到）

```
src     : C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py
          103900 字节 / 2546 行 / sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8
patched : 是

== --prove-dispatch：本地仿真（临时目录 + 替身模块，不连网、不写 src）==
  PASS  HOOK-E：exp 分支之前接管 -> 620 B（200）hook='HOOK-E'，名字表 43 项
  PASS  HOOK-E：protocol_name='NetworkTime_Sync' / gen_kind='networktime-3'
  PASS  外层 protocol == 'NetworkTime_Sync'
  PASS  内层 ReceiveTick == EchoSendTick == 639304751889441290（非 0）
  PASS  内层 RequestId == 外层 requestid（bfa7ef1c）
  PASS  内层 7 键（官方结构）：7
  PASS  ServerTimeTicks - ReceiveTick = 0 ticks（0..100000 = 0..10 ms，官方 12）
  PASS  HOOK-D：path D 的 `if proto_int:` 之前接管 -> 620 B（200）hook='HOOK-D'（HOOK-E 摘掉后）
  PASS  HOOK-D：rec.gen_kind='networktime-3'（不再是 min-envelope 的 {"Protocol":3}）
  PASS  外层 protocol == 'NetworkTime_Sync'
  PASS  内层 ReceiveTick == EchoSendTick == 639304751889441290（非 0）
  PASS  内层 RequestId == 外层 requestid（1d6ce00d）
  PASS  内层 7 键（官方结构）：7
  PASS  ServerTimeTicks - ReceiveTick = 0 ticks（0..100000 = 0..10 ms，官方 12）
  PASS  HOOK-G：正常分发（无 req_Hash，HOOK-E 摘掉）-> 620 B，hook='HOOK-G'
  PASS  HOOK-G：_generic_protocol_response() 里接管 -> 620 B，hook='HOOK-G'
  PASS  HOOK-G：gen_kind='networktime-3' / tick_delta=0
  PASS  异常隔离：生成器抛错 -> 仍是 200 / 448 B（== 打补丁前的 448 B），没有 500
  PASS  异常隔离：rec.p3_err="HOOK-G RuntimeError('injected generator failure')"（留痕，不会静默）
  PASS  开关缺失(=关)：回 200 / 448 B == 打补丁前 448 B（行为完全回退）
  PASS  开关缺失(=关)：rec.p3_off=3（判定为关并留痕）
  PASS  协议名兜底：请求片段没有 Hash 时仍回 620 B（p3_num 认 NetworkTime_Sync）

结论: 全绿：三层钩子都会被走到、异常只降级
```

### 步骤 6 `--rollback`（用备份还原）

```
src     : C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py
          103900 字节 / 2546 行 / sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8
patched : 是
已用备份还原: C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py.p3.bak.20261117-011931
  还原后 90585 字节 / sha256 368aa5e70941c3f08c59a9ede1b662331e5800dc0a714bc0a30dfbf252dd073a
  残留 BAPATCH-P3 标记: 无（干净）
```
独立复核：

```
size=90585  sha256=368aa5e70941c3f08c59a9ede1b662331e5800dc0a714bc0a30dfbf252dd073a
（= 基线，逐字节相同；回滚后 --verify 也回到「未打补丁」态，见下）
```
```
src     : C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py
          90585 字节 / 2212 行 / sha256 368aa5e70941c3f08c59a9ede1b662331e5800dc0a714bc0a30dfbf252dd073a
patched : 否
  INFO  src = C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py  (90585 字节 / 2212 行 / sha256 368aa5e70941c3f0)
  INFO  状态 = 未打补丁（校验基线+锚点）
  PASS  python 语法检查 compile() 
  PASS  基线大小 == 90585（实测 90585）
  PASS  基线 sha256 == 368aa5e70941c3f0（实测 368aa5e70941c3f0）
  PASS  锚点 HOOK-E 唯一命中 1 次（第 1677 行，_bridge() 里协议名解析完、`if exp == 'experror':` 之前）
  PASS  锚点 HOOK-D 唯一命中 1 次（第 1827 行，_bridge() 的 path D，`if proto_int:` 之前）
  PASS  锚点 HOOK-G 唯一命中 1 次（第 1353 行，_generic_protocol_response() 里，`if num == 90004:` 之前）
  PASS  锚点 PAYLOAD 唯一命中 1 次（第 2206 行，bridge 顶层，`if __name__ == '__main__':` 之前）
  PASS  基线里没有 BAPATCH-P3 残留标记
  INFO  未打补丁，跳过 P3_ORDER 比对（spec 键序 = ['Protocol', 'SessionKey', 'ServerTimeTicks', 'ServerNotification', 'RequestId', 'ReceiveTick', 'EchoSendTick']）
结论: PASS
```

## 5. 脚本 CLI 一览

```
python patch_3.py --src <bridge> --verify            # 自检：基线 sha256 / 锚点 / 载荷口径 / 620 B
python patch_3.py --src <bridge> --dry-run           # 打印插入位置 + 代码全文 + diff，不写
python patch_3.py --src <bridge> --apply             # 备份 -> 写 -> 语法 -> 自检 -> 建开关
python patch_3.py --src <bridge> --prove-dispatch    # 三层 hook 是否真被走到（本地仿真）
python patch_3.py --src <bridge> --rollback          # 用 .p3.bak.* 还原（无备份则摘块）
python _p3_replay.py  --target <bridge>              # 独立重放验收（22 项断言）
```

| 选项 | 说明 |
|---|---|
| `--src` | **必填**，不存在立即报错退出（不会去猜沙箱副本）|
| `--switches keep/1/0` | `cn_3.txt` 处理；`keep`=已有不动、缺失建 `1` |
| `--switch-dir` | 开关目录；默认线上路径 → `/www/wwwroot/bapatch`，其它路径 → src 所在目录 |
| `--restore F` / `--from-block-removal` / `--force` | 回滚细则 |
| `--full-diff` | `--dry-run` 时连载荷正文一起 diff |
| `--expect-sha` | 覆盖基线 sha256 期望（线上若已被别的补丁改过时用）|

## 6. 回滚

```bash
# 1) 关开关（最快，零风险，不用重启就生效于下一个请求）
echo 0 > /www/wwwroot/bapatch/cn_3.txt

# 2) 用备份还原整个文件（需要重启 bridge）
cp -a /www/wwwroot/bapatch/tools/account_auth_probe.py.p3.bak.<ts> \
      /www/wwwroot/bapatch/tools/account_auth_probe.py

# 3) 或者用脚本（自动挑 sha256 == 基线的那个备份）
python3 patch_3.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --rollback

# 4) 没有备份时也能摘块（幂等，只摘 BAPATCH-P3-* 四块）
python3 patch_3.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --rollback --from-block-removal
```

三种回滚都在本地实测过：`--rollback` 用 `.p3.bak.*` 还原后 **90,585 B / `368aa5e7…`**，
与基线逐字节相同，`--verify` 回到「未打补丁」态。
另外两条健壮性也实测了：**重复 `--apply` 幂等**（整块替换，输出 sha256 不变）、
**不依赖备份的摘块回滚**（`--from-block-removal`）也能精确回到基线字节：

```
== apply #1 ==
  写入后 103900 字节 / sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8
自检: 全绿
h1=563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8 (103900 B)
== apply #2 (idempotency) ==
  PAYLOAD: 替换已有块（旧 296 行 -> 新 296 行，幂等）
  HOOK-E: 替换已有块（旧 15 行 -> 新 15 行，幂等）
  HOOK-D: 替换已有块（旧 12 行 -> 新 12 行，幂等）
  HOOK-G: 替换已有块（旧 11 行 -> 新 11 行，幂等）
  写入后 103900 字节 / sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8
自检: 全绿
h2=563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8 (103900 B)  idempotent=True
== rollback --from-block-removal (does not use backup) ==
  PAYLOAD: 摘掉第 2244-2539 行（296 行）
  HOOK-E: 摘掉第 1690-1704 行（15 行）
  HOOK-D: 摘掉第 1838-1849 行（12 行）
  HOOK-G: 摘掉第 1353-1363 行（11 行）
  摘块回滚完成。备份=C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py.p3.bak.20261117-012153
  残留 BAPATCH-P3 标记: 无（干净）
after=90585 B / 368aa5e70941c3f08c59a9ede1b662331e5800dc0a714bc0a30dfbf252dd073a
equals_baseline=True
```

## 7. 上线步骤（交给 srv-ops；本 agent 未执行任何一步）

### 7.1 顺序

```bash
# 0) 备份 + 记指纹（现在是 90585 / 368aa5e7…）
cd /www/wwwroot/bapatch/tools
cp -a account_auth_probe.py account_auth_probe.py.p3.pre.$(date +%Y%m%d-%H%M%S)
sha256sum account_auth_probe.py

# 1) 上传 patch_3.py 到 tools/（或 deploy/），先自检（不写文件）
python3 patch_3.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --verify
python3 patch_3.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --dry-run

# 2) 先建开关 = 0（灰度：代码上去但行为不变）
printf "0\n" > /www/wwwroot/bapatch/cn_3.txt
python3 patch_3.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py \
        --apply --switches 0

# 3) 重启 bridge（代码改动必须重启才生效；原来是 pid 2538845 在跑）
#    用你们既有的启动方式重启后再继续

# 4) 打开开关（不需要再重启）
printf "1\n" > /www/wwwroot/bapatch/cn_3.txt

# 5) 本地复算 + 服务器端复算
python3 patch_3.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --verify
python3 _p3_replay.py --target /www/wwwroot/bapatch/tools/account_auth_probe.py
python3 patch_3.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --prove-dispatch
```

> `--switches keep`（默认）在文件缺失时会建 `1`；想灰度就用 `--switches 0` 显式写 `0`。
> 开关是**每请求实时读文件**，所以开/关都不用重启；只有替换 `account_auth_probe.py` 本体需要重启。

### 7.2 期望的落地指纹

| 项 | 值 |
|---|---|
| 大小 | **103,900 B**（若线上基线被别的补丁动过，字节数会不同，但 `--verify` 照样逐项判）|
| sha256 | `563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8`（沙箱实测值，仅作参考）|
| 新增标记 | `BAPATCH-P3-PAYLOAD` / `BAPATCH-P3-HOOK-E` / `-HOOK-D` / `-HOOK-G` 各一对 |

### 7.3 客户端侧验收

| 观测点 | 期望 |
|---|---|
| `api/networktime/sync` 的响应字节数 | **620**（原 536）|
| 日志 `rec.gen_kind` | `networktime-3` |
| 日志 `rec.p3_hook` | `HOOK-E`（正常）/ `HOOK-G`（名字表未命中）|
| 日志 `rec.p3_tick_delta` | `0`（红线：两个 tick 相等）|
| 日志 `rec.p3_ticks_mode` | `local` |
| 日志 `rec.p3_off` | 开关关时才有（=3）|
| 日志 `rec.p3_err` | 不应出现；出现即说明降级了，把原文贴回来 |
| 客户端行为 | 协议 3 之后继续发下一个请求（1005 / 4000 / 1017 …）|

### 7.4 万一 620 没出现，按这个顺序查

1. **开关**：`cat /www/wwwroot/bapatch/cn_3.txt` 是不是 `1`（缺失=关）。
2. **重启了没**：改的是文件，跑的是内存里的旧代码。
3. **走没走到 hook**：日志里 `rec.p3_hook` / `rec.p3_err` / `rec.fallback` 三个字段直接指明分支。
4. **时区**：`rec.p3_ticks` 解出来应该≈北京时间；若明显差 8 小时，`echo utc > cn_3_ticks.txt` 反过来试。
5. 以上都不对 → `--rollback`（或用 §6 的备份），行为立即回到 536。

## 8. 已知不确定 / 风险

| # | 项 | 影响 | 处置 |
|---|---|---|---|
| R1 | 线上 536 的确切来源（本地仿真同样的文件给 448）| 若它来自我没想到的分支，hook 可能不生效 | 三层 hook 覆盖了 path A/D/泛接口；**上线后看 `gen_kind`**，一行日志定生死 |
| R2 | 那台机器的系统时区不是 +08 | tick 差 8 小时，倒计时错乱 | `cn_3_ticks.txt` 写 `utc` 一行切换 |
| R3 | 客户端 `Hash` 结构变化导致 `num != 3` | 退回通用构造 | `p3_num()` 同时认「外层协议名 == NetworkTime_Sync」，不依赖 Hash |
| R4 | 线上基线被别的补丁改过（sha256 不是 `368aa5e7…`）| `--verify` 会 FAIL | `--expect-sha <实际值>` 或直接用 `--verify` 看锚点是否仍唯一 |
| R5 | 内嵌载荷与 `gen3.py` 漂移 | 回包结构退化 | `--verify` 每次都拿 `gen3.build_3()` 逐字节比；bridge 内嵌副本也逐字节比 `P3_PAYLOAD_SRC` |
| R6 | 本机无 `cryptography`，620 是「容器算式 + 等长替身」证明的 | 理论长度不变，但没在真机跑过真 AES | 上线后看 bridge 实际回包 / 客户端日志里的 resp 字节数（应 620）即闭环 |

## 9. 交付物清单

| 文件 | 大小 | sha256 |
|---|---|---|
| `work/ba/server/deploy/patch_3.py` | 63870 B | `09584f25fc93777ae795eb2acf6f40e3a2af4cebf9988b3a2506b978ea1f7ef4` |
| `work/ba/server/deploy/_p3_replay.py` | 12541 B | `65946b813d8d46c1866a4dde8ef0bdb8ee42023cc2c80f10a604538599100556` |
| `work/ba/server/deploy/PROGRESS_3_NETWORKTIME.md` | 59356 B | `4850c45042e33b04ac5a5884f2ca2b4a1f8adc3a093877b6dfb68951c30be5da` |

| 现场证据 | 路径 |
|---|---|
| 官方 04_3 抓包（结构基准）| `report/_tmp/official_decoded_201/04_3_api_networktime_sync.response.json` |
| gen3.py（真生成器，4099 B / `55a6cd57…`）| `work/ba/server/deploy/gen3.py` |
| 沙箱副本与各步骤原始日志 | `work/ba/server/deploy/_sandbox/p3/account_auth_probe.py + `seq/step*.txt`` |

---

*本文所有输出均为本地真实运行结果；未连接服务器、未执行 ssh/scp、未修改线上任何文件。*
