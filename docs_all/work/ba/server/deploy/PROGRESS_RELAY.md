# PROGRESS_RELAY — 未知协议「转发给本地 Shittim」补丁

> 生成：2026-11-17 01:5x（本地沙箱，未连接任何服务器）  
> 工作目录：`C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy`  
> 解释器：`<py>` = `C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`（3.12.14）

## 0. 一句话

`patch_relay.py` 在 `_bridge()` 的 `if name is None:` 分支里插一个 hook：开关（`cn_relay_unknown.txt`）打开时，把客户端真实请求解出来、注入 `ensure_session()` 拿到的真 SessionKey、`POST /api/gateway` 给本地 Shittim，再用 `self._cn_envelope(proto_str, obj, rec)` 把 Shittim 的真响应包成 CN 信封返回；任何一步不成就落回原来的 `min+base` 空壳，绝不 500。**开关默认缺失 = 关**，所以「打了补丁但不改行为」。

交付物：

| 文件 | 字节 | sha256 |
|---|---|---|
| `patch_relay.py` | 54297 | `3fe9a1687d5d2c091646be5758eecdd1f8cef59bfbc6b490f8bc000fa414c197` |
| `_relay_replay.py` | 38134 | `ce55d10ef4b20313c242a8dd692dd47df9c091d99a8e6464d9171baff0b2aff2` |

补丁产物（= 基线 + 本补丁）：**115,911 B / `377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07`**。

---

## 1. 基线重建（已确证，第一步）

线上 bridge = `90,585 B / 368aa5e7…`（patch_3 之前的基线）+ `patch_3.py --apply` = `103,900 B / 563c1942…`。本补丁**只认这后一份**。实测：

```text
cd work\ba\server\deploy
<py> patch_3.py --src _sandbox\p3\account_auth_probe.py --apply
# 期望：103,900 B / sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8
# 实测：103900 / 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8  -> 一致
```

若 `sha256` 不是 `563c1942…`，`patch_relay.py --apply` 会直接拒绝写入（见 `main()` 里的指纹闸）。

---

## 2. 锚点与插入位置

**基线（103,900 B）里的原文**：

```python
1714:        if name is None:
1715:            rec['unknown_protocol'] = True
1716:            got = self._generic_protocol_response(proto_str, packet_b64, rec)
1717:            if got is not None:
1718:                return got
1719:            code, resp, ctype = self._forward(body)
1720:            rec['fallback'] = 'forward-unknown-protocol'
```

**锚点**（`--verify` 断言各唯一命中 1 次）：

| unit | 锚点 | 出现次数 | 行号 | 插入方式 |
|---|---|---|---|---|
| HOOK-A | `        if name is None:\n            rec['unknown_protocol'] = True\n` | 1 | 1714 | after（插在其后） |
| PAYLOAD | `if __name__ == '__main__':\n` | 1 | 2540 | before |

**补丁后行号**（115,911 B / 2,832 行）：

| 内容 | 行号 |
|---|---|
| `if name is None:` | 1714 |
| `rec['unknown_protocol'] = True` | 1715 |
| **HOOK-A**（15 行） | **1716–1730** |
| `got = self._generic_protocol_response(proto_str, packet_b64, rec)` | 1731 |
| **PAYLOAD**（270 行） | **2555–2824** |
| `if __name__ == '__main__':` | 2825 |

> ⚠ 缩进坑：`rec['unknown_protocol'] = True` 在 `if name is None:` 的**函数体里**（12 空格），所以 HOOK-A 必须 12 空格缩进。8 空格缩进不会报语法错，但会跑到分支外面对**所有**协议生效 —— 本次实现时真踩到过，`--verify` 现在有「起始行缩进 12 空格 + AST 在 if 块内」两条断言，_relay_replay 的 R5 会从行为上再抓一次。

---

## 3. 插入代码全文

### 3.1 HOOK-A（插在第 1716–1730 行）

```python
            # >>> BAPATCH-RELAY-HOOK-A v1 BEGIN >>>
            # 未知协议：开关打开时把解出来的客户端真实请求转发给本地 Shittim
            # (/api/gateway)，拿到 dict 回包就用 _cn_envelope 包成 CN 信封返回。
            # 任何一步不成就原路落回（下面的 min+base / forward 完全不变，绝不 500）。
            # 已知协议（含 3/1005/1017/1019/24000/26000/4000/90004）在 relay_route
            # 里由 RL_HANDLED 显式排除；Account_CheckNexon(1014) 只由 ensure_session
            # 内部调用，不会经过这里。开关 cn_relay_unknown.txt 缺失 = 关。
            try:
                _rl_a = rl_route(rec, proto_str, packet_b64, name, self._cn_envelope)
                if _rl_a is not None:
                    return _rl_a
            except Exception as _rl_a_err:
                rec['relay_err'] = repr(_rl_a_err)
                rec['relay_fallthrough'] = 'exception'
            # <<< BAPATCH-RELAY-HOOK-A v1 END <<<
```

### 3.2 PAYLOAD（插在第 2555–2824 行，运行时模块，`RL_*` / `rl_*` 前缀，只用标准库）

```python
# >>> BAPATCH-RELAY-PAYLOAD v1 BEGIN >>> (deploy/patch_relay.py 内嵌 RL_PAYLOAD_SRC，sha256=8db678f98cf18e39fca2e9fbde49838edf85f4b92e8053a3608346deb720b5a2) >>>
# -*- coding: utf-8 -*-
"""未知协议 -> 本地 Shittim 转发（bridge 运行时真源，patch_relay.py --verify 逐字节比对）。

问题：_bridge() 的 `if name is None:` 分支先调 _generic_protocol_response()，它只回
     {"Protocol":<num>, "ServerTimeTicks":…, "ServerNotification":0, …} 的 min+base
     空壳，不会把客户端真实请求送去 Shittim。8000 / 8006 / 90011 / 35003 / 16000 卡在这里。

做法（开关打开时）：
     ① cn_cipher.decode_packet(packet_b64, proto_str) 解出客户端真实请求；
     ② ensure_session(rec) 打 Account_CheckNexon(1014) 拿真 SessionKey 并注入；
     ③ post_gateway(req) POST 到本地 Shittim 的 /api/gateway；
     ④ unwrap_gateway_response(raw) 拿 dict；
     ⑤ bridge 自己的 _cn_envelope(proto_str, obj, rec) 包成 CN 信封返回。
     任何一步不成就 return None，原逻辑（min+base / forward）照旧，绝不 500。

红线：
  * RL_HANDLED 里的协议号（3/1005/1017/1019/24000/26000/4000/90004）**显式排除**。
    本机 protocol_names.txt 缺失时 24000 / 90004 的 name 也是 None，没有这张表，
    开关一开就会把它们从真生成器手里抢走。
  * Account_CheckNexon(1014) 在名字表里，结构上到不了本分支；RL_LOCAL.busy 再挡
    一层同线程重入（嵌套调用直接落回原逻辑，不死循环）。
  * 开关缺失/0 => 完全不改行为（fail-safe）。

开关查找顺序（与 p3_read_file / simple_read_switch 一致）：
    bridge 所在目录 -> /www/wwwroot/bapatch/tools -> /www/wwwroot/bapatch

日志字段（写进 rec）：relay_on / relay_used / relay_code / relay_resp_len /
    relay_protocol / relay_err / relay_fallthrough
  辅助：relay_protocol_num / relay_num / relay_frag_len / relay_shittim_keys /
    relay_session_injected / relay_gateway_protocol / relay_account_id

约定（原样贴进 bridge 模块命名空间）：
  * 不写 from __future__，不写 __main__ 块；
  * 只用标准库，全部用 _rl* 别名 import，不污染 bridge 现有全局名；
  * import 期不碰文件系统、不碰网络；bridge 依赖一律 globals().get() 运行时取。
"""
import json as _rljson
import os as _rlos
import re as _rlre
import threading as _rlthreading

RL_SWITCH_FILE = 'cn_relay_unknown.txt'
RL_FALLBACK_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')
# 有真生成器 / 别的 hook 负责的协议号：本 hook 一律不碰（名字表缺名字时尤其重要）
RL_HANDLED = frozenset((3, 1005, 1017, 1019, 24000, 26000, 4000, 90004))
RL_SKIP_NAMES = frozenset(('Account_CheckNexon',))
RL_LOCAL = _rlthreading.local()


# ---------------------------------------------------------------- 开关
def rl_dirs():
    """开关文件的候选目录（有序）。"""
    out = []
    try:
        out.append(_rlos.path.dirname(_rlos.path.abspath(__file__)))
    except Exception:
        pass
    for d in RL_FALLBACK_DIRS:
        if d not in out:
            out.append(d)
    return out


def rl_read_file(fn, base=None):
    """读一个小开关文件 -> (路径, 内容)。找不到 -> (None, None)。"""
    dirs = ([base] if base else []) + rl_dirs()
    for d in dirs:
        if not d:
            continue
        p = _rlos.path.join(d, fn)
        try:
            with open(p, 'r') as fh:
                return p, fh.read().strip()
        except Exception:
            continue
    return None, None


def rl_switch_on(base=None):
    """未知协议转发是否启用。缺失 / 读不到 / 内容不是真值 -> False（fail-safe）。"""
    _p, v = rl_read_file(RL_SWITCH_FILE, base)
    if v is None:
        return False
    return v.strip().lower() in ('1', 'on', 'true', 'yes')


# ---------------------------------------------------------------- 请求重建
def rl_num_from_frag(frag):
    """协议号 = 请求里 Hash 的高 32 位（客户端每个请求都自带 Hash）。"""
    if not isinstance(frag, str) or not frag:
        return None
    m = _rlre.search(r'"Hash"\s*:\s*(\d+)', frag)
    if not m:
        return None
    try:
        return int(m.group(1)) >> 32
    except Exception:
        return None


def rl_request_json(decoded, rec=None):
    """cn_cipher.decode_packet() 的结果 -> 可发给 Shittim 的请求 dict；失败 -> None。

    decode_packet 的 'json' 只在它认识 protocol token 时才填（参照实现
    report/_tmp/mx_crypto/cn_cipher.py 的 PROTOCOL_MAP 只有 Account_Auth 一条）；
    而本 hook 面对的正是「名字表里没有」的 token，所以 'json' 常常是 None。
    这时用 'fragment'（客户端明文片段，形如 ',"Hash":…,"IsTest":false}'）拼回
    完整请求：'{"Protocol":<num>' + fragment。Protocol 用数字，交给 Shittim 的
    enum 反序列化（它本来就接受数字与名字两种写法）。
    """
    if not isinstance(decoded, dict):
        return None
    js = decoded.get('json')
    if isinstance(js, dict) and js:
        return js
    frag = decoded.get('fragment')
    if not isinstance(frag, str):
        return None
    text = frag.strip()
    if not text:
        return None
    if text[0] == '{':
        try:
            obj = _rljson.loads(text)
        except Exception:
            return None
        return obj if isinstance(obj, dict) else None
    num = rl_num_from_frag(text)
    if num is None and isinstance(rec, dict):
        h = rec.get('req_Hash')
        if isinstance(h, int) and h > 0:
            num = h >> 32
    if num is None:
        return None
    try:
        obj = _rljson.loads('{"Protocol":%d' % int(num) + text)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def rl_num_from_request(decoded, req=None):
    """协议号：片段 Hash>>32 -> 请求 JSON 的 Hash >>32 -> 请求 JSON 的 Protocol(int)。"""
    num = None
    if isinstance(decoded, dict):
        num = rl_num_from_frag(decoded.get('fragment'))
    if num is None and isinstance(req, dict):
        h = req.get('Hash')
        if isinstance(h, int) and h > 0:
            num = h >> 32
        elif isinstance(h, str) and h.strip().isdigit():
            num = int(h.strip()) >> 32
    if num is None and isinstance(req, dict):
        p = req.get('Protocol')
        if isinstance(p, int) and p > 0:
            num = p
    return num


# ---------------------------------------------------------------- 转发管线
def rl_route(rec, proto_str, packet_b64, name=None, envelope=None, base=None):
    """未知协议的接管线。已接管 -> (code, body, ctype)；不管 -> None（交回原兜底）。

    envelope 必须注入（bridge 传 self._cn_envelope）：
        envelope(proto_str, inner_obj, rec) -> (code, body, ctype)
    任何异常都不在这里吞：由 HOOK-A 的 try/except 兜住并记 rec['relay_err']。
    """
    if not isinstance(rec, dict):
        rec = {}
    on = bool(rl_switch_on(base))
    rec['relay_on'] = on
    rec['relay_err'] = ''
    if not on:
        rec['relay_fallthrough'] = 'switch-off'
        return None
    if isinstance(name, str) and name and name != 'Unknown':
        rec['relay_fallthrough'] = 'known-name'
        return None
    if isinstance(name, str) and name in RL_SKIP_NAMES:
        rec['relay_fallthrough'] = 'skip-name'
        return None
    if getattr(RL_LOCAL, 'busy', False):
        rec['relay_fallthrough'] = 'reentrant'
        return None
    RL_LOCAL.busy = True
    try:
        return _rl_relay_once(rec, proto_str, packet_b64, envelope)
    finally:
        RL_LOCAL.busy = False


def _rl_relay_once(rec, proto_str, packet_b64, envelope):
    """真正干活的只有这一段；异常往上抛（HOOK-A 负责留痕 + 落回）。"""
    dec = globals().get('cn_cipher')
    if dec is None or not hasattr(dec, 'decode_packet'):
        rec['relay_err'] = 'cn_cipher.decode_packet unavailable'
        rec['relay_fallthrough'] = 'no-cn_cipher'
        return None
    try:
        decoded = dec.decode_packet(packet_b64, proto_str)
    except Exception as e:
        rec['relay_err'] = repr(e)
        rec['relay_fallthrough'] = 'decode'
        return None
    req = rl_request_json(decoded, rec)
    if not isinstance(req, dict):
        rec['relay_fallthrough'] = 'decode-json'
        return None
    rec['relay_frag_len'] = len(decoded.get('fragment') or '') if isinstance(decoded, dict) else 0
    num = rl_num_from_request(decoded, req)
    rec['relay_num'] = num
    if num is None:
        rec['relay_fallthrough'] = 'no-protocol-num'
        return None
    if num in RL_HANDLED:
        # 3/1005/1017/1019/24000/26000/4000/90004 有真生成器：绝不抢
        rec['relay_fallthrough'] = 'handled-%d' % num
        return None
    ensure = globals().get('ensure_session')
    post = globals().get('post_gateway')
    unwrap = globals().get('unwrap_gateway_response')
    if not (callable(ensure) and callable(post) and callable(unwrap)):
        rec['relay_err'] = ('bridge deps missing: ensure_session=%r post_gateway=%r '
                            'unwrap_gateway_response=%r'
                            % (callable(ensure), callable(post), callable(unwrap)))
        rec['relay_fallthrough'] = 'no-deps'
        return None
    sk, aid = ensure(rec)
    if sk is None:
        rec['relay_fallthrough'] = 'ensure-session'
        return None
    injected = not req.get('SessionKey')
    if injected:
        req['SessionKey'] = sk
    rec['relay_session_injected'] = bool(injected)
    rec['relay_account_id'] = aid
    code, raw = post(req)
    raw = raw or b''
    rec['relay_code'] = code
    rec['relay_resp_len'] = len(raw)
    if code == 0:
        rec['relay_err'] = 'gateway unreachable/timeout: %r' % (raw[:160],)
        rec['relay_fallthrough'] = 'gateway-code-0'
        return None
    gp, obj = unwrap(raw)
    if isinstance(gp, (str, int)) or gp is None:
        rec['relay_gateway_protocol'] = gp
    else:
        rec['relay_gateway_protocol'] = repr(gp)
    if not isinstance(obj, dict):
        rec['relay_err'] = ('shittim response not dict (code=%r len=%d body=%r)'
                            % (code, len(raw), raw[:160]))
        rec['relay_fallthrough'] = 'shittim-non-dict'
        return None
    rec['relay_protocol'] = req.get('Protocol') if req.get('Protocol') is not None else num
    rec['relay_protocol_num'] = num
    if isinstance(obj.get('Protocol'), int):
        rec['relay_shittim_protocol'] = obj.get('Protocol')
    rec['relay_shittim_keys'] = len(obj)
    out = None
    if callable(envelope):
        out = envelope(proto_str, obj, rec)
    if out is None:
        rec['relay_fallthrough'] = 'envelope'
        return None
    rec['relay_used'] = True
    rec['relay_fallthrough'] = ''
    return out
# <<< BAPATCH-RELAY-PAYLOAD v1 END <<<
```

---

## 4. 设计要点（为什么这么写）

### 4.1 `RL_HANDLED` 排除表 —— 不是可选项

本机没有 `/www/wwwroot/bapatch/tools/protocol_names.txt`，`NAME_TABLE` 只有 43 个 `BUILTIN_NAMES` —— 里面**没有** `Academy_GetInfo` / `Management_Data` / `Item_List` / `Content_SaveGet`，所以 **24000、90004 在本机/在这种状态下 `name` 也是 `None`**，同样会走 `if name is None:`。没有排除表，开关一开就会把 academy-24000、management-90004 从真生成器手里抢走去转发 —— 直接违反「已知协议逐字节不变」。

因此 `rl_route()` 解出协议号后第一件事就是查 `RL_HANDLED = {3, 1005, 1017, 1019, 24000, 26000, 4000, 90004}`，命中就 `relay_fallthrough = 'handled-N'` 原路落回。`_relay_replay` 的 R5 用 9 个已知协议（含 4000/1005/26000/3/1017/24000/90004）逐个证明：`relay_used` 不存在、响应与摘掉本补丁的 legacy 逐字段一致。

### 4.2 为什么还要自己用 `fragment` 拼回请求

任务书给的 path A 写法是 `r = cn_cipher.decode_packet(...)` → `req_json = r.get('json')`。但参照实现（`report/_tmp/mx_crypto/cn_cipher.py:35-37, 95-102`）的 `PROTOCOL_MAP` **只有 `Account_Auth` 一条**：`json` 是靠 `'{"Protocol":"%s"' % name + fragment` 拼出来的，**名字反查不到时 `json` 就是 `None`** —— 而本 hook 面对的恰恰全是「名字表里没有」的 token。

所以 `rl_request_json()` 保留了两条路：

1. `decode_packet` 给了 dict → 直接用（与 path A 完全同源）；
2. `json` 是 `None` → 用 `fragment`（客户端明文片段 `,\"Hash\":…,\"IsTest\":false}`）拼回 `{"Protocol":<Hash>>32` + fragment，交给 Shittim 的 enum 反序列化（它本来就同时接受数字与名字）。

`_relay_replay` 的 R2（`json=None` 的真机口径）和 R7（`json` 有值的活服务器口径）分别覆盖这两条。

### 4.3 SessionKey / 重入 / 开关

- `ensure_session(rec)` 打 `Account_CheckNexon(1014)` 拿真 SessionKey（走 `post_gateway` 直连 Shittim，不经过 bridge）；请求里没有/为 null 时才注入，已有非空值不覆盖（与 path A 同语义）。
- `Account_CheckNexon` 本身在 `NAME_TABLE` 里 → 结构上到不了 `if name is None:`；`rl_route` 再按 `RL_SKIP_NAMES` 挡一次，并用 `RL_LOCAL.busy` 挡住同线程嵌套（`reentrant`）。
- 开关查找顺序照 `p3_read_file`：`dirname(__file__)` → `/www/wwwroot/bapatch/tools` → `/www/wwwroot/bapatch`；内容 `1/on/true/yes` 才算开，缺失/0/读不到一律关（fail-safe）。

### 4.4 外信封口径（照任务书）

响应出口就是任务书指定的 `self._cn_envelope(proto_str, obj, rec)`（bridge 自己的 CN 信封，不另写一套）。默认 `cn_proto_val()` 是 `token`，所以外层 `protocol` = `b32md5(proto_str)`；若要外层直接等于客户端发来的 token，把 `/www/wwwroot/bapatch/cn_proto_val.txt` 写成 `name` 即可（同一处开关，全站生效）。实测里 `rec.cn_env_protocol` 和响应外层 `protocol` 一致。

---

## 5. 六步验证（真实命令与输出）

### 5.1 第 1 步：`--verify`（基线指纹 + 锚点唯一）

```text
<py> patch_relay.py --src _sandbox\p3\account_auth_probe.py --verify
src     : _sandbox\p3\account_auth_probe.py
          103900 字节 / 2546 行 / sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8
patched : 否
  INFO  src = _sandbox\p3\account_auth_probe.py  (103900 字节 / 2546 行 / sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8)
  INFO  状态 = 未打补丁（校验基线+锚点）
  PASS  python 语法检查 compile() 
  PASS  基线大小 == 103900（实测 103900）
  PASS  基线 sha256 == 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8（实测 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8）
  PASS  基线里没有 BAPATCH-RELAY 残留标记
  PASS  基线确实是打过 patch_3 的 103900 B 版本（P3 载荷块在）
  PASS  锚点 PAYLOAD 唯一命中 1 次（第 2540 行，bridge 顶层，`if __name__ == '__main__':` 之前）
  PASS  锚点 HOOK-A 唯一命中 1 次（第 1714 行，_bridge() 的 name is None 分支里，`rec['unknown_protocol'] = True` 之后、`got = self._generic_protocol_response(...)` 之前）
  PASS  name is None 分支结构完好（anchor@68163 < got@68231）
  PASS  PAYLOAD 锚点在 name is None 分支之后（main@97777）
结论: PASS
```

### 5.2 第 2 步：`--dry-run`（打印插入位置与代码，mtime 不变）

实测 mtime/size：`mtime_before=639304481402837128 mtime_after=639304481402837128 same=True size=103900/103900`。

```text
<py> patch_relay.py --src _sandbox\p3\account_auth_probe.py --dry-run
src     : _sandbox\p3\account_auth_probe.py
          103900 字节 / 2546 行 / sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8
patched : 否

== 插入动作 ==
  PAYLOAD: 在原文件第 2540 行之前插入 270 行（锚点 "if __name__ == '__main__':"）
  HOOK-A: 在原文件第 1714-1715 行之后插入 15 行（锚点 'if name is None:'）
         -> 插入后 HOOK-A 落在第 1716 行之前（即 anchor 之后）

== 将要插入的位置 ==
  [PAYLOAD] 插到第 2540 行之前（bridge 顶层，`if __name__ == '__main__':` 之前）
  [HOOK-A] 插到第 1714-1715 行之后、第 1716 行之前（_bridge() 的 name is None 分支里，`rec['unknown_protocol'] = True` 之后、`got = self._generic_protocol_response(...)` 之前）

  ---- HOOK-A ----
              # >>> BAPATCH-RELAY-HOOK-A v1 BEGIN >>>
              # 未知协议：开关打开时把解出来的客户端真实请求转发给本地 Shittim
              # (/api/gateway)，拿到 dict 回包就用 _cn_envelope 包成 CN 信封返回。
              # 任何一步不成就原路落回（下面的 min+base / forward 完全不变，绝不 500）。
              # 已知协议（含 3/1005/1017/1019/24000/26000/4000/90004）在 relay_route
              # 里由 RL_HANDLED 显式排除；Account_CheckNexon(1014) 只由 ensure_session
              # 内部调用，不会经过这里。开关 cn_relay_unknown.txt 缺失 = 关。
              try:
                  _rl_a = rl_route(rec, proto_str, packet_b64, name, self._cn_envelope)
                  if _rl_a is not None:
                      return _rl_a
              except Exception as _rl_a_err:
                  rec['relay_err'] = repr(_rl_a_err)
                  rec['relay_fallthrough'] = 'exception'
              # <<< BAPATCH-RELAY-HOOK-A v1 END <<<

  ---- PAYLOAD 摘要 ----
  270 行 / sha256 8db678f98cf18e39
  头: # >>> BAPATCH-RELAY-PAYLOAD v1 BEGIN >>> (deploy/patch_relay.py 内嵌 RL_PAYLOAD_SRC，sha256=8db678f98cf18e39fca2e
  尾: # <<< BAPATCH-RELAY-PAYLOAD v1 END <<<

== diff（34 行）==
  --- _sandbox\p3\account_auth_probe.py
  +++ _sandbox\p3\account_auth_probe.py.patched
  @@ -1713,6 +1713,21 @@
   
           if name is None:
               rec['unknown_protocol'] = True
  +            # >>> BAPATCH-RELAY-HOOK-A v1 BEGIN >>>
  +            # 未知协议：开关打开时把解出来的客户端真实请求转发给本地 Shittim
  +            # (/api/gateway)，拿到 dict 回包就用 _cn_envelope 包成 CN 信封返回。
  +            # 任何一步不成就原路落回（下面的 min+base / forward 完全不变，绝不 500）。
  +            # 已知协议（含 3/1005/1017/1019/24000/26000/4000/90004）在 relay_route
  +            # 里由 RL_HANDLED 显式排除；Account_CheckNexon(1014) 只由 ensure_session
  +            # 内部调用，不会经过这里。开关 cn_relay_unknown.txt 缺失 = 关。
  +            try:
  +                _rl_a = rl_route(rec, proto_str, packet_b64, name, self._cn_envelope)
  +                if _rl_a is not None:
  +                    return _rl_a
  +            except Exception as _rl_a_err:
  +                rec['relay_err'] = repr(_rl_a_err)
  +                rec['relay_fallthrough'] = 'exception'
  +            # <<< BAPATCH-RELAY-HOOK-A v1 END <<<
               got = self._generic_protocol_response(proto_str, packet_b64, rec)
               if got is not None:
                   return got
  @@ -2537,6 +2552,9 @@
           rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
       return 200, wire, 'text/plain; charset=utf-8'
   # <<< BAPATCH-P3-PAYLOAD v1 END <<<
  +# >>> BAPATCH-RELAY-PAYLOAD v1 BEGIN >>> (deploy/patch_relay.py 内嵌 RL_PAYLOAD_SRC，sha256=8db678f98cf18e39fca2e9fbde49838edf85f4b92e8053a3608346deb720b5a2) >>>
  +# ...[268 行运行时模块原样内嵌自 patch_relay.py 的 RL_PAYLOAD_SRC，--full-diff 查看]...
  +# <<< BAPATCH-RELAY-PAYLOAD v1 END <<<
   if __name__ == '__main__':
       n = load_names()
       print('protocol name table =', n, 'entries')

语法检查: PASS
--dry-run：没有写文件。mtime/size 未变: True（(1794851340283712800, 103900)）
           开关文件也没动（正式执行时 --switches keep -> C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\cn_relay_unknown.txt）
```

### 5.3 第 3 步：`--apply --switches 1`（产物 py_compile + 开关文件）

```text
<py> patch_relay.py --src _sandbox\p3\account_auth_probe.py --apply --switches 1
src     : _sandbox\p3\account_auth_probe.py
          103900 字节 / 2546 行 / sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8
patched : 否

== 插入动作 ==
  PAYLOAD: 在原文件第 2540 行之前插入 270 行（锚点 "if __name__ == '__main__':"）
  HOOK-A: 在原文件第 1714-1715 行之后插入 15 行（锚点 'if name is None:'）
         -> 插入后 HOOK-A 落在第 1716 行之前（即 anchor 之后）

== diff（34 行）==
  --- _sandbox\p3\account_auth_probe.py
  +++ _sandbox\p3\account_auth_probe.py.patched
  @@ -1713,6 +1713,21 @@
   
           if name is None:
               rec['unknown_protocol'] = True
  +            # >>> BAPATCH-RELAY-HOOK-A v1 BEGIN >>>
  +            # 未知协议：开关打开时把解出来的客户端真实请求转发给本地 Shittim
  +            # (/api/gateway)，拿到 dict 回包就用 _cn_envelope 包成 CN 信封返回。
  +            # 任何一步不成就原路落回（下面的 min+base / forward 完全不变，绝不 500）。
  +            # 已知协议（含 3/1005/1017/1019/24000/26000/4000/90004）在 relay_route
  +            # 里由 RL_HANDLED 显式排除；Account_CheckNexon(1014) 只由 ensure_session
  +            # 内部调用，不会经过这里。开关 cn_relay_unknown.txt 缺失 = 关。
  +            try:
  +                _rl_a = rl_route(rec, proto_str, packet_b64, name, self._cn_envelope)
  +                if _rl_a is not None:
  +                    return _rl_a
  +            except Exception as _rl_a_err:
  +                rec['relay_err'] = repr(_rl_a_err)
  +                rec['relay_fallthrough'] = 'exception'
  +            # <<< BAPATCH-RELAY-HOOK-A v1 END <<<
               got = self._generic_protocol_response(proto_str, packet_b64, rec)
               if got is not None:
                   return got
  @@ -2537,6 +2552,9 @@
           rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
       return 200, wire, 'text/plain; charset=utf-8'
   # <<< BAPATCH-P3-PAYLOAD v1 END <<<
  +# >>> BAPATCH-RELAY-PAYLOAD v1 BEGIN >>> (deploy/patch_relay.py 内嵌 RL_PAYLOAD_SRC，sha256=8db678f98cf18e39fca2e9fbde49838edf85f4b92e8053a3608346deb720b5a2) >>>
  +# ...[268 行运行时模块原样内嵌自 patch_relay.py 的 RL_PAYLOAD_SRC，--full-diff 查看]...
  +# <<< BAPATCH-RELAY-PAYLOAD v1 END <<<
   if __name__ == '__main__':
       n = load_names()
       print('protocol name table =', n, 'entries')

语法检查: PASS

已写入。备份: _sandbox\p3\account_auth_probe.py.relay.bak.20261117-015234
  写入后 115911 字节 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
  还原命令: cp -a _sandbox\p3\account_auth_probe.py.relay.bak.20261117-015234 _sandbox\p3\account_auth_probe.py
  （或 python patch_relay.py --src _sandbox\p3\account_auth_probe.py --rollback）
开关: C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\cn_relay_unknown.txt=1（新建）

== 打完补丁后的自检 ==
  ...（63 条 PASS 省略，完整见日志）...
  PASS  cn_cipher.decode_packet 抛错 -> None + relay_err="ValueError('bad packet')"
自检: 全绿
```

**幂等复跑**（同一文件再 `--apply`）：

```text
<py> patch_relay.py --src _sandbox\p3\account_auth_probe.py --apply --switches keep
src     : _sandbox\p3\account_auth_probe.py
          115911 字节 / 2831 行 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
patched : 是

== 插入动作 ==
  PAYLOAD: 替换已有块（旧 270 行 -> 新 270 行，幂等）
  HOOK-A: 替换已有块（旧 15 行 -> 新 15 行，幂等）

== diff（0 行）==

语法检查: PASS

已写入。备份: _sandbox\p3\account_auth_probe.py.relay.bak.20261117-015234
  写入后 115911 字节 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
  还原命令: cp -a _sandbox\p3\account_auth_probe.py.relay.bak.20261117-015234 _sandbox\p3\account_auth_probe.py
  （或 python patch_relay.py --src _sandbox\p3\account_auth_probe.py --rollback）
开关: C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\cn_relay_unknown.txt='1'（保留，未改动）

== 打完补丁后的自检 ==
  INFO  src = _sandbox\p3\account_auth_probe.py  (115911 字节 / 2831 行 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07)
  INFO  状态 = 已打补丁（校验补丁后不变量）
  PASS  python 语法检查 compile() 
  PASS  PAYLOAD 标记成对、各 1 处（BEGIN 1 / END 1）
  PASS  HOOK-A 标记成对、各 1 处（BEGIN 1 / END 1）
  PASS  内嵌 PAYLOAD 逐字节 == patch_relay.py 的 RL_PAYLOAD_SRC（sha256 8db678f98cf18e39 / 8db678f98cf18e39）
  PASS  PAYLOAD 标记里记的 sha256 与真源一致（8db678f98cf18e39）
  PASS  HOOK-A 代码块逐字节 == patch_relay.py 里生成的那份
  PASS  HOOK-A 落在 `if name is None:` 之内：none@68163 < flag@68188 < hook@68243 < got@69045
  PASS  HOOK-A 起始行缩进 12 空格（在 name is None 的分支体内，不是函数体层）
  PASS  HOOK-A 紧跟在 `rec[unknown_protocol] = True` 之后（上一行 = "            rec['unknown_protocol'] = True"）
  PASS  AST：HOOK-A 确实在 `if name is None:` 的语法块里（不只是文本位置对）
  PASS  HOOK-A 调用了 rl_route(...) 且注入 self._cn_envelope
  PASS  PAYLOAD 在 `if __name__ == '__main__':` 之前（payload@98591 < main@108280）
  PASS  既有补丁 BAPATCH-P3-PAYLOAD 仍在（未被动过）
  PASS  既有补丁 BAPATCH-P3-HOOK-E 仍在（未被动过）
  PASS  既有补丁 BAPATCH-P3-HOOK-D 仍在（未被动过）
  PASS  既有补丁 BAPATCH-P3-HOOK-G 仍在（未被动过）
  PASS  既有补丁 BAPATCH-SIMPLE-PAYLOAD 仍在（未被动过）
  PASS  既有补丁 BAPATCH-SIMPLE-HOOK-D 仍在（未被动过）
  PASS  既有补丁 BAPATCH-SIMPLE-HOOK-G 仍在（未被动过）
  PASS  摘掉 PAYLOAD+HOOK-A 后逐字节 == 基线 103900 B / sha256 563c1942289968e3（实测 103900 B / 563c1942289968e3）
  PASS  摘块后零 BAPATCH-RELAY 残留
  PASS  内嵌载荷可 exec
  PASS  开关查找顺序 == bridge 目录 -> /www/wwwroot/bapatch/tools -> /www/wwwroot/bapatch（['C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\server\\deploy', '/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch']）
  PASS  开关文件缺失 -> 判定「关」（fail-safe）
  PASS  cn_relay_unknown.txt=1 -> True
  PASS  cn_relay_unknown.txt=0 -> False
  PASS  cn_relay_unknown.txt=on -> True
  PASS  cn_relay_unknown.txt=yes -> True
  PASS  cn_relay_unknown.txt=空 -> False
  PASS  删除开关文件 -> 又变回「关」
  PASS  Hash>>32 -> 协议号 8000
  PASS  空片段 / None -> 协议号 None（不抛）
  PASS  decode_packet 给了 'json' -> 直接用它（与 path A 同源）
  PASS  cn_cipher 不认识 token（json=None）-> 用 fragment 拼回 {"Protocol":8000,…}（['AccountId', 'Hash', 'IsTest', 'Protocol']）
  PASS  片段为空 -> None（落回原逻辑）
  PASS  片段没有 Hash 时用 rec[req_Hash] 补协议号（{'Protocol': 90004, 'IsTest': False}）
  PASS  坏片段不抛异常（返回 None 或 dict）
  PASS  rl_num_from_request 优先级：片段 Hash 优先
  PASS  开关关：rl_route -> None（relay_on=False / fallthrough=switch-off）
  PASS  开关开但没有 cn_cipher -> None + relay_err 留痕（'cn_cipher.decode_packet unavailable'）
  PASS  协议号 3 有真生成器 -> 本 hook 不碰（fallthrough='handled-3'）
  PASS  协议号 1005 有真生成器 -> 本 hook 不碰（fallthrough='handled-1005'）
  PASS  协议号 1017 有真生成器 -> 本 hook 不碰（fallthrough='handled-1017'）
  PASS  协议号 1019 有真生成器 -> 本 hook 不碰（fallthrough='handled-1019'）
  PASS  协议号 24000 有真生成器 -> 本 hook 不碰（fallthrough='handled-24000'）
  PASS  协议号 26000 有真生成器 -> 本 hook 不碰（fallthrough='handled-26000'）
  PASS  协议号 4000 有真生成器 -> 本 hook 不碰（fallthrough='handled-4000'）
  PASS  协议号 90004 有真生成器 -> 本 hook 不碰（fallthrough='handled-90004'）
  PASS  RL_HANDLED 覆盖 3 / 24000 / 90004（名字表缺名字时也不会被抢）
  PASS  name 已知 -> 不接管（fallthrough=known-name）
  PASS  同线程重入保护：busy=True -> 不接管（fallthrough=reentrant）
  PASS  开关开 + 全链路替身 -> 返回 _cn_envelope 的 (200, body, ctype)
  PASS  relay_used=True / relay_on=True
  PASS  relay_protocol=8000 / relay_protocol_num=8000（协议号取自 Hash>>32）
  PASS  relay_code=200 / relay_resp_len=78
  PASS  SessionKey 缺省时注入（relay_session_injected=True）
  PASS  发给 Shittim 的请求带 Protocol=8000（8000）
  PASS  响应经 self._cn_envelope(proto_str, obj, rec) 出口（proto_str='TOKEN_8000', keys=['Echo', 'Protocol']）
  PASS  请求里已有 SessionKey -> 不覆盖（relay_session_injected=False）
  PASS  ensure_session 回 None（1014 失败）-> 落回原逻辑（fallthrough=ensure-session）
  PASS  Shittim 回 500 -> None + relay_err='shittim response not dict (code=500 len=16 body=b\'{"error":"boom"}\')'（落回 min+base，不 500）
  PASS  Shittim 超时（post_gateway 回 code 0）-> None + relay_err='gateway unreachable/timeout: b\'{"error":"timed out"}\''
  PASS  cn_cipher.decode_packet 抛错 -> None + relay_err="ValueError('bad packet')"
自检: 全绿
```

两次写入 sha256 相同 = `377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07`：整块替换是幂等的。`cn_relay_unknown.txt` 建在 `_sandbox\p3\cn_relay_unknown.txt`（= `switch_dir_for()` 报告的位置），内容 `1`。

### 5.4 第 4 步：回归三连（必须全绿、不受影响）

```text
<py> patch_3.py --src _sandbox\p3\account_auth_probe.py --verify
```

```text
src     : _sandbox\p3\account_auth_probe.py
          115911 字节 / 2831 行 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
patched : 是
  INFO  src = _sandbox\p3\account_auth_probe.py  (115911 字节 / 2831 行 / sha256 377176809ff25949)
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
  PASS  HOOK-D 在 path D 的 `if proto_int:` 之前（hook@75787 < anchor@76346）
  PASS  HOOK-E 在协议名解析之后、exp 分支之前（name@66920 < hook@66964 < exp@67703）
  PASS  PAYLOAD 在 `if __name__ == '__main__':` 之前（payload@88798 < anchor@108280）
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
结论: PASS
```

```text
<py> _p3_replay.py --target _sandbox\p3\account_auth_probe.py
```

```text
target : _sandbox\p3\account_auth_probe.py
         115911 字节 / sha256 377176809ff25949
patched: 是

== 重放断言 ==
  INFO  A0   响应体 = base64(密文+key)（620 B），外层明文 430 B
  PASS  A1   外层 protocol == 'NetworkTime_Sync'（实测 'NetworkTime_Sync'）
  PASS  A1   HTTP 200 / Content-Type 'text/plain; charset=utf-8'（官方同款 text/plain）
  PASS  A2   wire 字节数 == 620（实测 620）
  PASS  A2   base64(密文+key32) 形态成立：raw 464 B = ct 432 B + key 32 B
  PASS  A3   内层键序 == 官方 top_key_order（7 键）
  PASS  A3   内层键序 == official_spec.json protocols["3"].top_key_order
  PASS  A4   ReceiveTick 是真时间戳（639304771550849680，非 0）
  PASS  A4   ReceiveTick == EchoSendTick（红线）：639304771550849680 == 639304771550849680
  PASS  A5   ServerTimeTicks - ReceiveTick = 0 ticks（0..100000 即 0..10 ms）
  PASS  A6   内层 RequestId == 外层 requestid 且是 uuid 形态（5457590b）
  PASS  A7   ReceiveTick 解回 2026-11-17 01:52:35.084968，与现在 2026-11-17 01:52:35 差 0.0 s（<180 s）
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

```text
<py> patch_3.py --src _sandbox\p3\account_auth_probe.py --prove-dispatch
```

```text
src     : _sandbox\p3\account_auth_probe.py
          115911 字节 / 2831 行 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
patched : 是

== --prove-dispatch：本地仿真（临时目录 + 替身模块，不连网、不写 src）==
  PASS  HOOK-E：exp 分支之前接管 -> 620 B（200）hook='HOOK-E'，名字表 43 项
  PASS  HOOK-E：protocol_name='NetworkTime_Sync' / gen_kind='networktime-3'
  PASS  外层 protocol == 'NetworkTime_Sync'
  PASS  内层 ReceiveTick == EchoSendTick == 639304771552077530（非 0）
  PASS  内层 RequestId == 外层 requestid（38685484）
  PASS  内层 7 键（官方结构）：7
  PASS  ServerTimeTicks - ReceiveTick = 0 ticks（0..100000 = 0..10 ms，官方 12）
  PASS  HOOK-D：path D 的 `if proto_int:` 之前接管 -> 620 B（200）hook='HOOK-D'（HOOK-E 摘掉后）
  PASS  HOOK-D：rec.gen_kind='networktime-3'（不再是 min-envelope 的 {"Protocol":3}）
  PASS  外层 protocol == 'NetworkTime_Sync'
  PASS  内层 ReceiveTick == EchoSendTick == 639304771552077530（非 0）
  PASS  内层 RequestId == 外层 requestid（1110f846）
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

### 5.5 第 5 步：`_relay_replay.py`（假 Shittim，45 项断言）

本地起 `http.server`（`127.0.0.1:0` 随机端口）实现 `/api/gateway`：

- `Account_CheckNexon` → `{"Protocol":1014,"ResultState":1,"SessionKey":{"AccountServerId":2,"MxToken":"<64 字符 base64>"},"AccountId":2}`
- 其它协议 → `{"Protocol":<num>,"Echo":[<请求体的键>]}`
- 可切 `error500` / `hang`（超时）

```text
<py> _relay_replay.py --target _sandbox\p3\account_auth_probe.py
target : _sandbox\p3\account_auth_probe.py
         115911 字节 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
patched: 是

== 重放断言 ==
  PASS  R0   摘掉 PAYLOAD+HOOK-A 后 == 基线 103900 B / 563c1942289968e3（实测 103900 B / 563c1942289968e3）
  PASS  R0   HOOK-A 落在 name is None 分支内（none@68163 < hook@68243 < got@69045）
  PASS  R0   锚点 `if name is None:` + `rec['unknown_protocol'] = True` 未被改动
  INFO  R1   未知协议 token = b32md5('Mission_List_CN_8000') = QNPPDSGNIUGHKQLQV3YJOSNSLI（NAME_TABLE 里查不到 = True）
  PASS  R1   开关关：8000 -> 200 / gen_kind='min+base'（min+base 空壳）
  PASS  R1   开关关：unknown_protocol=True 且没有 relay_used 字段
  PASS  R1   开关关：relay_on=False / relay_fallthrough='switch-off'
  PASS  R1   开关关：内层仍是假壳 Protocol=8000
  PASS  R1   开关关：假 Shittim 一次都没被调用（0 次）
  PASS  R1   开关关：响应与摘掉本补丁的 legacy 逐字段一致（掩 uuid 后）
  PASS  R1   开关关：原始字节 '差 0 B'（uuid 每次不同，故以掩码对照为准）
  PASS  R2   开关开：8000 -> 200，relay_used=True / relay_on=True
  PASS  R2   relay_protocol=8000 / relay_protocol_num=8000（= Hash>>32）
  PASS  R2   内层是假 Shittim 的真响应（Protocol=8000 / Echo=['AccountId', 'Hash', 'IsTest', 'Protocol']）
  PASS  R2   relay_code=200 / relay_resp_len=108
  PASS  R2   SessionKey 由 ensure_session(1014) 注入（relay_session_injected=True）
  PASS  R2   假 Shittim 收到 1014=1 次 / 8000=1 次（先铸会话再转发，各一次）
  PASS  R2   转发请求里的 SessionKey == Shittim 铸的那张（AccountServerId=2 / MxToken 64 字符）
  PASS  R2   外层 protocol == _cn_envelope 的 cn_env_protocol（'W4MSIPTS2XKU43KS6DGX7WA4S4'）
  PASS  R2   开关开后的响应 != 开关关时的 min+base 空壳（真的换了数据源）
  PASS  R10  成功路径的 7 个日志字段齐备
  PASS  R3   Shittim 回 500 -> bridge 仍 200 / gen_kind='min+base'（relay_used 不存在）
  PASS  R3   relay_code=500 / relay_err='shittim response not dict (code=500 len=36 body=b\'{"error":"injected-shittim-failure"}\')'
  PASS  R3   落回的内层是 min+base 空壳（Protocol=8000）
  PASS  R3b  _cn_envelope 抛异常 -> bridge 仍 200 / fallthrough='exception' / relay_err="RuntimeError('injected-envelope-boom')"
  PASS  R3c  ensure_session 回 None -> bridge 仍 200 / fallthrough='ensure-session'（不 500）
  PASS  R4   Shittim 超时 -> bridge 仍 200 / gen_kind='min+base'（2.0 s 内返回）
  PASS  R4   relay_err='gateway unreachable/timeout: b\'{"error":\\\'timed out\\\'}\''（耗时 2.0 s < 10 s）
  PASS  R7   cn_cipher 给了 json（活服务器可能如此）-> 仍走同一条转发管线（relay_used=True / 内层 Protocol=8000）
  PASS  R9   8006 -> Shittim 真响应（relay_protocol=8006 / 内层 Protocol=8006）
  PASS  R9   90011 -> Shittim 真响应（relay_protocol=90011 / 内层 Protocol=90011）
  PASS  R9   35003 -> Shittim 真响应（relay_protocol=35003 / 内层 Protocol=35003）
  PASS  R9   16000 -> Shittim 真响应（relay_protocol=16000 / 内层 Protocol=16000）
  PASS  R8   同一线程已在转发（busy=True）-> 直接落回（fallthrough='reentrant' / Shittim 0 次）
  PASS  R6   Account_CheckNexon(1014) -> 200 / 内层 Protocol=1014
  PASS  R6   1014 只被调用 1 次（0.00 s）、rec 里没有任何 relay_* 字段（[]）—— 无递归
  PASS  R5   Account_Auth(1002)：开关开 vs legacy 一致（gen_kind=None / relay_used 不存在 / fallthrough=None / legacy 自身可复现=True）
  INFO  R5     ↳ Account_Auth(1002) rec relay_* = []（只允许 on/err/fallthrough 这类访问痕迹）
  PASS  R5   Account_CheckNexon(1014)：开关开 vs legacy 一致（gen_kind=None / relay_used 不存在 / fallthrough=None / legacy 自身可复现=True）
  INFO  R5     ↳ Account_CheckNexon(1014) rec relay_* = []（只允许 on/err/fallthrough 这类访问痕迹）
  PASS  R5   Item_List(4000)：开关开 vs legacy 一致（gen_kind='simple-4000' / relay_used 不存在 / fallthrough='handled-4000' / legacy 自身可复现=True / 字节仅差时间-uuid）
  INFO  R5     ↳ Item_List(4000) rec relay_* = ['relay_err', 'relay_fallthrough', 'relay_frag_len', 'relay_num', 'relay_on']（只允许 on/err/fallthrough 这类访问痕迹）
  PASS  R5   Account_GetTutorial(1005)：开关开 vs legacy 一致（gen_kind='simple-1005' / relay_used 不存在 / fallthrough=None / legacy 自身可复现=True / 字节仅差时间-uuid）
  INFO  R5     ↳ Account_GetTutorial(1005) rec relay_* = []（只允许 on/err/fallthrough 这类访问痕迹）
  PASS  R5   Content_SaveGet(26000)：开关开 vs legacy 一致（gen_kind='simple-26000' / relay_used 不存在 / fallthrough='handled-26000' / legacy 自身可复现=True / 字节仅差时间-uuid）
  INFO  R5     ↳ Content_SaveGet(26000) rec relay_* = ['relay_err', 'relay_fallthrough', 'relay_frag_len', 'relay_num', 'relay_on']（只允许 on/err/fallthrough 这类访问痕迹）
  PASS  R5   NetworkTime_Sync(3)：开关开 vs legacy 一致（gen_kind='networktime-3' / relay_used 不存在 / fallthrough=None / legacy 自身可复现=True / 字节仅差时间-uuid）
  INFO  R5     ↳ NetworkTime_Sync(3) rec relay_* = []（只允许 on/err/fallthrough 这类访问痕迹）
  PASS  R5   Account_LoginSync(1017)：开关开 vs legacy 一致（gen_kind='loginsync-1017-dynamic' / relay_used 不存在 / fallthrough=None / legacy 自身可复现=True / 字节仅差时间-uuid）
  INFO  R5     ↳ Account_LoginSync(1017) rec relay_* = []（只允许 on/err/fallthrough 这类访问痕迹）
  PASS  R5   Academy_GetInfo(24000)：开关开 vs legacy 一致（gen_kind='academy-24000-v3' / relay_used 不存在 / fallthrough='handled-24000' / legacy 自身可复现=True / 字节仅差时间-uuid）
  INFO  R5     ↳ Academy_GetInfo(24000) rec relay_* = ['relay_err', 'relay_fallthrough', 'relay_frag_len', 'relay_num', 'relay_on']（只允许 on/err/fallthrough 这类访问痕迹）
  PASS  R5   Management_Data(90004)：开关开 vs legacy 一致（gen_kind='management-90004' / relay_used 不存在 / fallthrough='handled-90004' / legacy 自身可复现=True / 字节仅差时间-uuid）
  INFO  R5     ↳ Management_Data(90004) rec relay_* = ['relay_err', 'relay_fallthrough', 'relay_frag_len', 'relay_num', 'relay_on']（只允许 on/err/fallthrough 这类访问痕迹）
  INFO  R5   9 个已知协议里 2 个原始字节完全相同，其余仅差 ServerTimeTicks/uuid/时间字符串（掩码后全部逐字段一致；legacy 自身两次运行也在同一批字段上不同）
  PASS  R11  全程只监听 127.0.0.1:55955（假 Shittim），未连任何远端

45 项断言 / 0 FAIL / ALL PASS
```

### 5.6 第 6 步：`--rollback`（回到 `563c1942…`，零残留）

```text
<py> patch_relay.py --src _sandbox\p3\account_auth_probe.py --rollback
src     : _sandbox\p3\account_auth_probe.py
          115911 字节 / 2831 行 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
patched : 是
  跳过备份 account_auth_probe.py.relay.bak.20261117-015234（sha256 377176809ff25949 不是基线 563c1942289968e3）
  PAYLOAD: 摘掉第 2555-2824 行（270 行）
  HOOK-A: 摘掉第 1716-1730 行（15 行）
  摘块回滚完成。备份=_sandbox\p3\account_auth_probe.py.relay.bak.20261117-015237
  还原后 103900 字节 / sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8
  残留 BAPATCH-RELAY 标记: 无（干净）
```

回滚后复验：

```text
<py> patch_relay.py --src _sandbox\p3\account_auth_probe.py --verify
src     : _sandbox\p3\account_auth_probe.py
          103900 字节 / 2546 行 / sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8
patched : 否
  INFO  src = _sandbox\p3\account_auth_probe.py  (103900 字节 / 2546 行 / sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8)
...
结论: PASS
```

### 5.7 附加：CLI 边界自测（`--expect-sha` / 指纹闸 / 无备份回滚）

```text
### A) --verify --expect-sha <正确基线>

  PASS  基线 sha256 == 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8（实测 563c1942289968e3f402c52eb89982
cba75f9753ba85d13f6cca0be244ffc5c8）
结论: PASS
exit=0

### B) --verify --expect-sha <错误值>（必须 FAIL）
  FAIL  基线 sha256 == 0000000000000000000000000000000000000000000000000000000000000000（实测 563c1942289968e3f402c52eb89982
cba75f9753ba85d13f6cca0be244ffc5c8）
结论: FAIL
exit=1

### C) 对 90,585 B 原始基线 --apply（必须拒绝，且不改文件）
!! 基线指纹不符，拒绝打补丁
   实测 90585 字节 / sha256 368aa5e70941c3f08c59a9ede1b662331e5800dc0a714bc0a30dfbf252dd073a
   期望 103900 字节 / sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8（= 基线 368aa5e70941c3f08c59a9ed
e1b662331e5800dc0a714bc0a30dfbf252dd073a + patch_3 v1）
   确认无误可加 --expect-sha <实测sha> 或 --force。
exit=1
old.py 仍是 90585 B

### D) --apply --switches keep（文件缺失时必须不创建 = 保持关）
  写入后 115911 字节 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
开关: _scratch\cli_t\sw\cn_relay_unknown.txt（缺失，未创建 —— 缺失=关；要开启用 --switches 1，要显式写 0 用 --switches 0）
自检: 全绿
switch 文件存在 = False（期望 False）

### E) --apply 后删掉备份，再 --rollback --from-block-removal（只能靠摘块）
  写入后 115911 字节 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
自检: 全绿
apply size=115911
  PAYLOAD: 摘掉第 2555-2824 行（270 行）
  HOOK-A: 摘掉第 1716-1730 行（15 行）
  还原后 103900 字节 / sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8
  残留 BAPATCH-RELAY 标记: 无（干净）
final size=103900 / sha=563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8
```

---

## 6. 回滚命令

```bash
# 沙箱
<py> patch_relay.py --src _sandbox\p3\account_auth_probe.py --rollback
# 线上（会优先找 sha256 == 563c1942 的 .relay.bak.*，否则整块摘除）
<py> patch_relay.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --rollback
# 硬要不用备份：
<py> patch_relay.py --src <file> --rollback --from-block-removal
# 顺手把开关关掉（不删文件）：
echo 0 > /www/wwwroot/bapatch/cn_relay_unknown.txt
```

`--rollback` 两种路径都做过：备份还原（上面第 6 步）与整块摘除（`--verify` 里「摘掉 PAYLOAD+HOOK-A 后逐字节 == 基线」+ `_relay_replay` R0 各断言一次）。

---

## 7. 「开关打开后未知协议会拿到真 Shittim 数据」的信心依据

按证据强度从高到低：

1. **请求真的发到了 Shittim，且带着真 SessionKey。** `_relay_replay` R2 里假 Shittim 的调用记录显示：`Account_CheckNexon` 1 次 + 目标协议 1 次；目标协议那条的 `SessionKey` `== {"AccountServerId":2,"MxToken":"<64 字符>"}`，正是 CheckNexon 那张票；`relay_used=True`、`relay_code=200`、`relay_resp_len=108`。R9 对 8006 / 90011 / 35003 / 16000 逐个复现。
2. **回给客户端的是 Shittim 的响应体，不是本地构造。** 假 Shittim 故意回一个本地绝不会产生的 `Echo` 键；R2 断言响应的 CN 信封内层 `== {"Protocol":8000,"Echo":[...]}`。若 bridge 没转发，`min+base` 的内层只有 8 个假键、没有 `Echo`（R1 同时证明了这一点）。
3. **`post_gateway` 这条路是线上已在用的同一条。** 同一个函数、同一个 `/api/gateway`、同一个 `cn_cipher.build_mx`，`ensure_session`（1014）与 `Account_Auth`（1002）今天就在用它；本补丁只是把「未知协议」也接到这条路上，没有新协议、没有新容器格式。
4. **失败一定落回，连错误都不会让客户端断线。** R3（Shittim 500）、R3b（信封构造抛异常）、R3c（`ensure_session` 回 None）、R4（Shittim 超时）、以及 `--verify` 里的 decode 抛错，全部是 `200 + min+base` 且 `relay_err` 非空；`_handle()` 的 500 分支根本没被触发。
5. **已知协议一行都没动。** HOOK-A 在 `if name is None:` 的语法块内（AST 断言），`RL_HANDLED` 又显式排除 8 个有真生成器的协议号；R5 的 9 个协议在开关打开时与 legacy 逐字段一致。

仍属推断、需要上线后看日志确认的两点（不影响「拿到的是 Shittim 数据」这个结论）：

- 客户端是否按外层 `protocol` 而不是内层 `Protocol` 匹配响应。当前线上 `min+base` 的外层是 `'Unknown'`（`_cn_send_envelope(name or 'Unknown')`），客户端当时也接受了 —— 说明它多半认内层；有了真数据后应看 `relay_*` 日志与客户端是否继续发下一个请求。
- Shittim 对「Protocol 用数字 + 缺字段」的容忍度：数字 enum 是 Newtonsoft 默认支持的，缺字段由 handler 自己决定；最坏情况是 Shittim 回 `Error` 信封（`Protocol:-1`），那也会被当成 dict 正常回给客户端 —— 需要按 `relay_gateway_protocol` / 内层 `Protocol` 判读。

---

## 8. 上线注意 / 已知限制

- **必须重启 bridge 才生效**（pid 见 `FALLBACK_QUEUE_20261117.md`），重启会踢掉在线客户端。
- 开关默认关：先 `--apply --switches keep`（**缺失时不创建** = 关；这点与 patch_3 的 keep 「缺失建 1」不同，是本补丁有意的差异），确认补丁在文件里、行为与现状一致，再 `echo 1 > /www/wwwroot/bapatch/cn_relay_unknown.txt` 打开（改开关**不用**重启）。
- Shittim 必须活着：它挂了就是「超时 → 落回 min+base」，不会更糟，但也拿不到数据。注意 hook 调的是 `post_gateway(req)`（默认 `timeout=40`，与 path A 完全一致），所以 Shittim 半死时最坏 40 s 才落回；要更短得改 bridge 里 `post_gateway` 的默认值，本补丁刻意不传 timeout，保持与 path A 同一口径。
- 内层 `RequestId` 没有补（`SHITTIM_ROOT_PLAN.md` §3.1 的 ⑦ 是独立改动）。本补丁只换数据源，不扩语义；要不要补 `RequestId` 应在看到客户端是否接受真响应之后再定。
- `Protocol` 以数字发给 Shittim（未知协议没有名字可发）；名字若以后从 `protocol_names.txt` 补进来，`name is None` 就不再成立，本 hook 自动不再介入 —— 这是期望行为。
- 沙箱最终状态：`_sandbox\p3\account_auth_probe.py` = **103,900 B / `563c1942…`**，`BAPATCH-RELAY` 标记 0 个；本次创建的 `cn_relay_unknown.txt` 与 `.relay.bak.*` 已清理。

---

## 9. 证据日志原件

| 步骤 | 文件 |
|---|---|
| 1 verify | `_scratch\seq1_verify.log` |
| 2 dry-run | `_scratch\seq2_dryrun.log` |
| 3 apply | `_scratch\seq3_apply.log` |
| 3b 幂等复跑 | `_scratch\seq3b_apply_again.log` |
| 4a patch_3 --verify | `_scratch\seq4a_p3verify.log` |
| 4b _p3_replay | `_scratch\seq4b_p3replay.log` |
| 4c --prove-dispatch | `_scratch\seq4c_prove.log` |
| 5 _relay_replay | `_scratch\seq5_replay.log` |
| 6 rollback | `_scratch\seq6_rollback.log` |
| 6b rollback 后 verify | `_scratch\seq6b_verify_after.log` |
| 7 CLI 边界自测 | `_scratch\seq7_cli.log` |

> 全部命令都在本地执行，未 ssh / scp / 连接任何服务器；`_relay_replay.py` 只监听 `127.0.0.1` 的随机端口。
