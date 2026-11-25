# PROGRESS_RELAY2 — 「名字已知、但没有真生成器」的协议转发给本地 Shittim

* 执行：2026-11-17（一次性执行 agent），工作目录 `work/ba/server/deploy`。
* **铁律遵守**：全程只在本地工作，没连服务器、没 ssh/scp；python 用
  `C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`（3.12.14）。
* 产物：`patch_relay2.py`（补丁）、`_relay2_replay.py`（62 项本地重放）、本文件。
* 沙箱最终状态：`_sandbox/p3/account_auth_probe.py` = **115,911 B /
  sha256 `377176809f…`**（= patch_3 v1 + patch_relay v1 的基线），零 `BAPATCH-RELAY2` 残留，
  开关文件与本次产生的备份都已清掉。

---

## 0. 一句话

上一版 `patch_relay.py` 的钩子挂在 `if name is None:` 里，只对「名字表里查不到」的协议生效；
`Mission_List`(8000) / `Account_SetTutorial`(1006) 这些名字**都在** 202 条名字表里，所以永远进不了那条分支，
只能拿 `min+base` 空壳（8000 线上 536 B / 官方同接口 268,396 B）。

这一版在 `_bridge()` 的 **`if proto_int:` 之前、与它同级（8 空格）** 再挂一个钩子，开关
`cn_relay_known.txt`（独立文件，默认缺失=关）打开时把请求转发给本地 Shittim，
8 秒超时，拿到 dict 就用 `self._cn_envelope(...)` 回。任何一步不成就**原路落回**原来的
`min+base` / `forward`，绝不 500；14 个「有专分支 / 有真生成器」的协议号硬排除。

---

## 1. 为什么要这一版（背景，已实测）

| 事实 | 证据 |
|---|---|
| `protocol_names.txt` 存在（2,434 B / 202 条名字） | 线上文件；本机没有这个文件（本地只有 `BUILTIN_NAMES` 43 条） |
| 8000 / 1006 的名字在表里 ⇒ `name is not None` | ⇒ 进不了 `if name is None:` ⇒ HOOK-A 永不执行 |
| 8000 线上回 536 B、90011/8006/35003/16000 回 512 B，`gen_kind=min+base` | `FALLBACK_QUEUE_20261117.md` 的 17 条登录序列日志 |
| Shittim 侧有全部 handler，8000 实测回 804 B 真数据 | 任务方实测（`proto 8000 -> {"protocol":"Mission_List","packet":"{…804 B…}"}`） |

**一条重要的更正（本次读代码确认）**：在本仓库这份 bridge 里，`rec['req_Hash']` 只在
path A（`decrypt+` 且解出 json dict）里赋值，所以 path D 的 `proto_int` 通常是 `None` ——
线上那 5 个 `gen_kind=min+base` 实际是走 `_generic_protocol_response()` 的 else 分支。
也就是说 path D 有**两条**空壳出口：

```
path D:
    proto_int = rec['req_Hash'] >> 32      # 通常 None
    ... HOOK-D(simple/p3) ...
    if proto_int:                          # ← 出口 ①：min-envelope 空壳
        return self._cn_send_envelope(...)
    got = self._generic_protocol_response(...)   # ← 出口 ②：min+base 空壳（线上实际走这条）
```

把钩子放在 `if proto_int:` **之前**，这两条出口就同时被罩住了（S2b 专门验证了 ①）。


---

## 2. 基线闸（唯一允许的基线）

```
work/ba/server/deploy/_sandbox/p3/account_auth_probe.py
    115,911 B / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
    = patch_3 v1（103,900 B / 563c1942…）+ patch_relay v1
```

复现（本次就是这么做的）：

```bash
cd work/ba/server/deploy
python patch_relay.py --src _sandbox/p3/account_auth_probe.py --apply --switches 1
# 必须得到 115,911 B / 377176809f…，不符就停
```

`patch_relay2.py` 的 `--verify` / `--apply` 都以这个指纹为硬闸：

* 未打补丁时：`len == 115911` 且 `sha256 == 377176809f…` 必须同时成立，否则 `--apply` 直接拒绝；
* 还额外断言 relay v1 的 `BAPATCH-RELAY-PAYLOAD` / `BAPATCH-RELAY-HOOK-A` 各存在 1 份，
  并且它的 `RL_PAYLOAD` 里确实有 `rl_read_file()` / `rl_request_json()` / `rl_num_from_request()`
  （relay2 复用的就是这三个）；
* 打完之后：摘掉 relay2 两块必须**逐字节**回到 115,911 B / `377176809f…`（`--rollback` 的依据）。

---

## 3. 钩子位置（锚点行号 / 缩进 / AST 三方证据）

**基线文件里的锚点**（`_sandbox/p3/account_auth_probe.py`，2,831 行）：

| 位置 | 行号 | 原文 |
|---|---|---|
| HOOK 锚点 `if proto_int:` | **1880–1881** | `        if proto_int:` + `            obj = cn_nick.build_min_response(proto_int)` |
| 上一行（结构钉） | 1879 | `        # <<< BAPATCH-P3-HOOK-D v1 END <<<` |
| PAYLOAD 锚点 `if __name__ == '__main__':` | **2825** | 顶格 |



**打完补丁之后**（128,309 B / 3,082 行）：

| 块 | 行号 | 行数 |
|---|---|---|
| HOOK（含 BEGIN/END） | **1880–1896** | 17 |
| `if proto_int:`（被推到） | **1897** | 8 空格缩进 |
| PAYLOAD（含 BEGIN/END） | **2842–3075** | 234 |
| `if __name__ == '__main__':` | **3076** | — |

### 缩进到底几层？（上一版踩过的坑，这一版钉死）

`if proto_int:` 在 `_bridge` 的**方法体**里 = **8 空格**（不是 12）。所以钩子的 `try:` 也必须 8 空格、
紧挨在它前面，钩子体内语句 12 空格。写成 12 空格会怎样？不会报语法错 —— 它会掉进上面
`P3-HOOK-D` 那个 `except Exception as _p3d_err:` 的**处理体**里，只有 `p3_wants()` 抛异常时才执行，
等于永远不生效，而且 `--verify` 的 AST 断言也抓不到（如果只查文本位置的话）。

`--verify` 因此有四重断言（全部 PASS，见 §5.1 / §5.3）：

1. 文本：`HOOK 起始行缩进 == 8 空格（实测 8）—— 与 if proto_int: **同级**`；
2. 文本：`HOOK 体内语句缩进 == 12 == 锚点缩进 + 1 层`；
3. AST：`rl2_route(...)` 所在 `Try` 是 `_bridge` 函数体里的**直接语句**，下标 `22`，
   `if proto_int:` 下标 `23`（即**直接前一条**），父节点 = `FunctionDef`（不是 `ExceptHandler`）；
4. **反证**：把整块右移 4 空格后重新 parse，AST 上父节点确实变成 `ExceptHandler`
   —— 证明第 3 条断言真能抓住这个坑。

另外 `--verify` 还断言 path D 的 7 行原文未被改动（`min+envelope` / `_generic_protocol_response` 原样），
以及 relay1 / simple / p3 的 9 个既有补丁块各 1 份仍在。


---

## 4. 插入代码全文

### 4.1 HOOK（17 行，8 空格缩进，插在第 1880 行之前）

```python
        # >>> BAPATCH-RELAY2-HOOK v1 BEGIN >>>
        # 名字已知、但没有真生成器的协议（8000 / 1006 / 8006 / 90011 / 35003 / 16000 …）：
        # 开关 cn_relay_known.txt 打开时，把客户端真实请求转发给本地 Shittim
        # (/api/gateway)，拿到 dict 回包就用 _cn_envelope 包成 CN 信封返回。
        # 挂在这里（`if proto_int:` 之前、同级）等于同时接住两条空壳出口：
        #   proto_int 有值 -> 原本走下面的 min-envelope；为 None -> 走 _generic_protocol_response 的 min+base。
        # 任何一步不成就原路落回（下面的代码完全不变，绝不 500）。
        # 有真生成器的协议号由 RL2_HANDLED 显式排除；Account_CheckNexon(1014) 只由
        # ensure_session 内部调用，另有名字级排除 + 同线程重入保护。开关缺失 = 关。
        try:
            _rl2_a = rl2_route(rec, proto_str, packet_b64, name, self._cn_envelope)
            if _rl2_a is not None:
                return _rl2_a
        except Exception as _rl2_a_err:
            rec['relay2_err'] = repr(_rl2_a_err)
            rec['relay2_fallthrough'] = 'exception'
        # <<< BAPATCH-RELAY2-HOOK v1 END <<<
```

### 4.2 PAYLOAD（234 行，顶格，插在 `if __name__ == '__main__':` 之前）

```python
# >>> BAPATCH-RELAY2-PAYLOAD v1 BEGIN >>> (deploy/patch_relay2.py 内嵌 RL2_PAYLOAD_SRC，sha256=cab63ac0e9c6e7440d6879dfda56df040385b821c76417ed38945df14532c32d) >>>
# -*- coding: utf-8 -*-
"""名字已知但没有真生成器的协议 -> 本地 Shittim 转发（bridge 运行时真源）。

为什么要这一版：patch_relay.py 的 HOOK-A 挂在 `if name is None:` 分支里，只对「名字表里
查不到」的协议生效。但 protocol_names.txt 里 Mission_List(8000) / Account_SetTutorial(1006)
这些名字都在，所以它们进不了那个分支，只能拿到 min+base 空壳。本模块的钩子挂在
`if proto_int:` **之前**（与它同级、都在 `_bridge` 的语句序列里），名字已知也照样接管。

做法（开关 cn_relay_known.txt 打开时）：
  ① cn_cipher.decode_packet(packet_b64, proto_str) 解出客户端真实请求（与 HOOK-A 同一个解码器）；
  ② 复用 relay v1 的 RL_PAYLOAD 里已经验证过的 rl_request_json / rl_num_from_request
     拼回发给 Shittim 的请求、取出协议号 —— 不另写一套；
  ③ ensure_session(rec) 打 Account_CheckNexon(1014) 拿真 SessionKey（缺才注入）；
  ④ post_gateway(req, timeout=8) POST 到本地 Shittim 的 /api/gateway。
     8 秒而不是默认 40 秒：这条路径每个请求都要走，40 秒会把客户端拖到超时；
  ⑤ unwrap_gateway_response(raw) -> dict 就用 self._cn_envelope(协议名, obj, rec) 返回。
     （传协议名不是 token：_cn_envelope 内部会算 base32(md5(名字))，那正好等于客户端
      请求里带的 token；传 token 会二次哈希，外层 protocol 就对不上了。）
  任何一步不成就 return None，原逻辑（if proto_int 的 min-envelope / min+base / forward）
  照旧，绝不 500。

红线：
  * RL2_HANDLED（1002/1014/1000/1009/1012/1019/2001/3/1005/1017/24000/26000/4000/90004）
    一律不碰：要么在更前面的分支已经 return（结构上到不了这里），要么有真生成器
    （24000 / 1017 / 90004 在 _generic_protocol_response 里）。排除表是双保险。
  * Account_CheckNexon 名字级排除 + RL2_LOCAL.busy 同线程重入保护：ensure_session 内部
    那次 1014 直接走 post_gateway、不经过 bridge，嵌套调用也被挡住，不会递归。
  * 开关缺失 / 不是真值 => 完全不改行为（fail-safe）。

依赖（运行时从 bridge 全局取，取不到就落回，不抛）：
    cn_cipher.decode_packet / ensure_session / post_gateway / unwrap_gateway_response
    rl_request_json / rl_num_from_request / rl_read_file（= patch_relay.py 的 RL_PAYLOAD）

开关查找顺序（委托 rl_read_file，与 patch_3 / patch_relay 一致）：
    bridge 所在目录 -> /www/wwwroot/bapatch/tools -> /www/wwwroot/bapatch

日志字段（写进 rec）：
    relay2_on / relay2_used / relay2_code / relay2_resp_len / relay2_protocol /
    relay2_err / relay2_fallthrough
  辅助：relay2_num / relay2_name / relay2_session_injected / relay2_account_id /
    relay2_gateway_protocol / relay2_shittim_protocol / relay2_shittim_keys

约定（原样贴进 bridge 模块命名空间）：
  * 不写 from __future__，不写 __main__ 块；
  * 只用标准库，全部 _rl2* 别名 import，不污染 bridge 现有全局名；
  * import 期不碰文件系统、不碰网络；bridge 依赖一律 globals().get() 运行时取。
"""
import os as _rl2os
import threading as _rl2threading

RL2_VER = 'v1'
RL2_SWITCH_FILE = 'cn_relay_known.txt'
RL2_FALLBACK_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')
# 转发超时：这条路径每个请求都走，必须短（默认 40 秒会让客户端超时）
RL2_TIMEOUT = 8
# 有真生成器 / 更前面的专分支负责的协议号：本 hook 一律不碰（双保险）
RL2_HANDLED = frozenset((1002, 1014, 1000, 1009, 1012, 1019, 2001, 3, 1005, 1017,
                         24000, 26000, 4000, 90004))
RL2_SKIP_NAMES = frozenset(('Account_CheckNexon', 'Account_Auth', 'Account_Auth2',
                            'Account_LoginSync', 'Account_Nickname', 'Account_CallName'))
RL2_LOCAL = _rl2threading.local()


# ---------------------------------------------------------------- 开关
def rl2_dirs():
    """开关文件的候选目录（有序）：bridge 目录 -> bapatch/tools -> bapatch。"""
    out = []
    try:
        out.append(_rl2os.path.dirname(_rl2os.path.abspath(__file__)))
    except Exception:
        pass
    for d in RL2_FALLBACK_DIRS:
        if d not in out:
            out.append(d)
    return out


def rl2_read_file(fn, base=None):
    """读一个小开关文件 -> (路径, 内容)。优先复用 relay v1 的 rl_read_file。"""
    rd = globals().get('rl_read_file')
    if callable(rd):
        try:
            return rd(fn, base)
        except Exception:
            pass
    dirs = ([base] if base else []) + rl2_dirs()
    for d in dirs:
        if not d:
            continue
        p = _rl2os.path.join(d, fn)
        try:
            with open(p, 'r') as fh:
                return p, fh.read().strip()
        except Exception:
            continue
    return None, None


def rl2_switch_on(base=None):
    """cn_relay_known.txt 是否打开。缺失 / 读不到 / 内容不是真值 -> False（fail-safe）。"""
    _p, v = rl2_read_file(RL2_SWITCH_FILE, base)
    if v is None:
        return False
    return v.strip().lower() in ('1', 'on', 'true', 'yes')


# ---------------------------------------------------------------- 转发管线
def rl2_route(rec, proto_str, packet_b64, name=None, envelope=None, base=None):
    """名字已知（但没有真生成器）的协议接管线。接管 -> (code, body, ctype)；不管 -> None。

    envelope 必须注入（bridge 传 self._cn_envelope）：
        envelope(协议名, inner_obj, rec) -> (code, body, ctype)
      （传**协议名**不是客户端 token：_cn_envelope 内部算 base32(md5(名字))，那才等于
        客户端请求里带的 token；传 token 会二次哈希。）
    任何异常都不在这里吞：由 HOOK 的 try/except 兜住并记 rec['relay2_err']。
    """
    if not isinstance(rec, dict):
        rec = {}
    on = bool(rl2_switch_on(base))
    rec['relay2_on'] = on
    rec['relay2_err'] = ''
    if not on:
        rec['relay2_fallthrough'] = 'switch-off'
        return None
    if isinstance(name, str) and name in RL2_SKIP_NAMES:
        rec['relay2_fallthrough'] = 'skip-name'
        return None
    if getattr(RL2_LOCAL, 'busy', False):
        rec['relay2_fallthrough'] = 'reentrant'
        return None
    RL2_LOCAL.busy = True
    try:
        return _rl2_relay_once(rec, proto_str, packet_b64, name, envelope)
    finally:
        RL2_LOCAL.busy = False


def _rl2_relay_once(rec, proto_str, packet_b64, name, envelope):
    """真正干活的只有这一段；异常往上抛（HOOK 负责留痕 + 落回）。"""
    dec = globals().get('cn_cipher')
    if dec is None or not hasattr(dec, 'decode_packet'):
        rec['relay2_err'] = 'cn_cipher.decode_packet unavailable'
        rec['relay2_fallthrough'] = 'no-cn_cipher'
        return None
    # 复用 patch_relay.py 的 RL_PAYLOAD：请求重建 / 协议号提取只信这一份实现
    req_builder = globals().get('rl_request_json')
    num_reader = globals().get('rl_num_from_request')
    if not (callable(req_builder) and callable(num_reader)):
        rec['relay2_err'] = ('relay v1 payload missing: rl_request_json=%r '
                             'rl_num_from_request=%r'
                             % (callable(req_builder), callable(num_reader)))
        rec['relay2_fallthrough'] = 'no-relay1'
        return None
    try:
        decoded = dec.decode_packet(packet_b64, proto_str)
    except Exception as e:
        rec['relay2_err'] = repr(e)
        rec['relay2_fallthrough'] = 'decode'
        return None
    req = req_builder(decoded, rec)
    if not isinstance(req, dict):
        rec['relay2_fallthrough'] = 'decode-json'
        return None
    num = num_reader(decoded, req)
    rec['relay2_num'] = num
    rec['relay2_name'] = name if isinstance(name, str) else None
    if num is None:
        rec['relay2_fallthrough'] = 'no-protocol-num'
        return None
    if num in RL2_HANDLED:
        # 1002/1014/3/1005/1017/24000/26000/4000/90004 … 有真生成器或专分支：绝不抢
        rec['relay2_fallthrough'] = 'handled-%d' % num
        return None
    ensure = globals().get('ensure_session')
    post = globals().get('post_gateway')
    unwrap = globals().get('unwrap_gateway_response')
    if not (callable(ensure) and callable(post) and callable(unwrap)):
        rec['relay2_err'] = ('bridge deps missing: ensure_session=%r post_gateway=%r '
                             'unwrap_gateway_response=%r'
                             % (callable(ensure), callable(post), callable(unwrap)))
        rec['relay2_fallthrough'] = 'no-deps'
        return None
    sk, aid = ensure(rec)
    if sk is None:
        rec['relay2_fallthrough'] = 'ensure-session'
        return None
    injected = not req.get('SessionKey')
    if injected:
        req['SessionKey'] = sk
    rec['relay2_session_injected'] = bool(injected)
    rec['relay2_account_id'] = aid
    try:
        code, raw = post(req, timeout=RL2_TIMEOUT)
    except TypeError:
        # 变体 bridge 的 post_gateway 可能没有 timeout 形参：退回默认总比 500 好
        code, raw = post(req)
    raw = raw or b''
    rec['relay2_code'] = code
    rec['relay2_resp_len'] = len(raw)
    if code == 0:
        rec['relay2_err'] = 'gateway unreachable/timeout: %r' % (raw[:160],)
        rec['relay2_fallthrough'] = 'gateway-code-0'
        return None
    gp, obj = unwrap(raw)
    if gp is None or isinstance(gp, (str, int)):
        rec['relay2_gateway_protocol'] = gp
    else:
        rec['relay2_gateway_protocol'] = repr(gp)
    if not isinstance(obj, dict):
        rec['relay2_err'] = ('shittim response not dict (code=%r len=%d body=%r)'
                             % (code, len(raw), raw[:160]))
        rec['relay2_fallthrough'] = 'shittim-non-dict'
        return None
    rec['relay2_protocol'] = req.get('Protocol') if req.get('Protocol') is not None else num
    rec['relay2_protocol_num'] = num
    if isinstance(obj.get('Protocol'), int):
        rec['relay2_shittim_protocol'] = obj.get('Protocol')
    rec['relay2_shittim_keys'] = len(obj)
    out = None
    # 注意：bridge 的 _cn_envelope(proto_name, ...) 会自己算 base32(md5(proto_name))，
    # 客户端请求里带的正是 base32(md5(协议名))。所以这里必须传**协议名**，不能传客户端
    # 的 token —— 传 token 会变成 b32md5(b32md5(name))，外层 protocol 就和客户端对不上了。
    proto_name = name if (isinstance(name, str) and name and name != 'Unknown') else proto_str
    rec['relay2_envelope_name'] = proto_name
    if callable(envelope):
        out = envelope(proto_name, obj, rec)
    if out is None:
        rec['relay2_fallthrough'] = 'envelope'
        return None
    rec['relay2_used'] = True
    rec['relay2_fallthrough'] = ''
    return out
# <<< BAPATCH-RELAY2-PAYLOAD v1 END <<<
```

> PAYLOAD 与 `patch_relay2.py` 里的 `RL2_PAYLOAD_SRC` **逐字节相同**（`--verify` 每次都比对，
> 并把 sha256 写在 BEGIN 标记行里）。

---

## 5. 六步验证的真实输出

> 全部是本地命令的真实 stdout（PowerShell 控制台按 GBK 显示会有乱码，这里保留 UTF-8 原文）。
> 原始文件：`_scratch/seq_relay2/step*.txt`。

### 5.1 `--verify`（未打补丁的基线）

```text
$ python patch_relay2.py --src _sandbox\p3\account_auth_probe.py --verify
src     : _sandbox\p3\account_auth_probe.py
          115911 字节 / 2831 行 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
patched : 否
  INFO  src = _sandbox\p3\account_auth_probe.py  (115911 字节 / 2831 行 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07)
  INFO  状态 = 校验基线+锚点
  PASS  python 语法检查 compile() 
  PASS  基线大小 == 115911（实测 115911）
  PASS  基线 sha256 == 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07（实测 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07）
  PASS  基线里没有 BAPATCH-RELAY2 残留（实测 0 处）
  PASS  relay v1 的 BAPATCH-RELAY-PAYLOAD v1 块在（BEGIN/END 各 1）
  PASS  relay v1 的 BAPATCH-RELAY-HOOK-A v1 块在（BEGIN/END 各 1）
  PASS  relay v1 的 RL_PAYLOAD 里确实有 rl_read_file()（relay2 复用的就是它）
  PASS  relay v1 的 RL_PAYLOAD 里确实有 rl_request_json()（relay2 复用的就是它）
  PASS  relay v1 的 RL_PAYLOAD 里确实有 rl_num_from_request()（relay2 复用的就是它）
  PASS  锚点 PAYLOAD 唯一命中 1 次（第 2825 行，bridge 顶层，`if __name__ == '__main__':` 之前）
  PASS  锚点 HOOK 唯一命中 1 次（第 1880 行，_bridge() 里 path D 的 `if proto_int:` **之前、同级**（8 空格），在 P3-HOOK-D 之后）
  PASS  path D 的 `if proto_int:` 分支 7 行原样在（唯一命中，结构性完好）
  PASS  锚点 `if proto_int:` 缩进 == 8 空格（实测 8）—— 钩子也必须 8 空格
  PASS  AST：`if proto_int:` 是 `_bridge` 函数体的一条**直接语句**（下标 22）
  PASS  AST：`if proto_int:` 的前一条语句是 Try（P3-HOOK-D，line 1870）—— 钩子就插在这一对之间
  PASS  PAYLOAD 锚点在 path D 之后（main@108280）
结论: PASS
```

### 5.2 `--dry-run`（打印插入位置与 diff，mtime 不变）

```text
$ python patch_relay2.py --src _sandbox\p3\account_auth_probe.py --dry-run
src     : _sandbox\p3\account_auth_probe.py
          115911 字节 / 2831 行 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
patched : 否

== 插入动作 ==
  PAYLOAD: 在原文件第 2825 行之前插入 234 行（锚点 "if __name__ == '__main__':"）
  HOOK: 在原文件第 1880-1881 行之前插入 17 行（锚点 'if proto_int:'）
         -> 插入后 HOOK 落在第 1880 行，紧挨在 `if proto_int:`（第 1897 行）之前，两者同为 8 空格缩进

== 将要插入的位置 ==
  [PAYLOAD] 插到第 2825 行之前（bridge 顶层，`if __name__ == '__main__':` 之前）
  [HOOK] 插到第 1880 行之前（_bridge() 里 path D 的 `if proto_int:` **之前、同级**（8 空格），在 P3-HOOK-D 之后）
        缩进 = 8 空格（与 `if proto_int:` 同级；体内 12 空格）

  ---- HOOK ----
          # >>> BAPATCH-RELAY2-HOOK v1 BEGIN >>>
          # 名字已知、但没有真生成器的协议（8000 / 1006 / 8006 / 90011 / 35003 / 16000 …）：
          # 开关 cn_relay_known.txt 打开时，把客户端真实请求转发给本地 Shittim
          # (/api/gateway)，拿到 dict 回包就用 _cn_envelope 包成 CN 信封返回。
          # 挂在这里（`if proto_int:` 之前、同级）等于同时接住两条空壳出口：
          #   proto_int 有值 -> 原本走下面的 min-envelope；为 None -> 走 _generic_protocol_response 的 min+base。
          # 任何一步不成就原路落回（下面的代码完全不变，绝不 500）。
          # 有真生成器的协议号由 RL2_HANDLED 显式排除；Account_CheckNexon(1014) 只由
          # ensure_session 内部调用，另有名字级排除 + 同线程重入保护。开关缺失 = 关。
          try:
              _rl2_a = rl2_route(rec, proto_str, packet_b64, name, self._cn_envelope)
              if _rl2_a is not None:
                  return _rl2_a
          except Exception as _rl2_a_err:
              rec['relay2_err'] = repr(_rl2_a_err)
              rec['relay2_fallthrough'] = 'exception'
          # <<< BAPATCH-RELAY2-HOOK v1 END <<<

  ---- PAYLOAD 摘要 ----
  234 行 / sha256 cab63ac0e9c6e744
  头: # >>> BAPATCH-RELAY2-PAYLOAD v1 BEGIN >>> (deploy/patch_relay2.py 内嵌 RL2_PAYLOAD_SRC，sha256=cab63ac0e9c6e7440d
  尾: # <<< BAPATCH-RELAY2-PAYLOAD v1 END <<<

== diff（36 行）==
  --- _sandbox\p3\account_auth_probe.py
  +++ _sandbox\p3\account_auth_probe.py.patched
  @@ -1877,6 +1877,23 @@
           except Exception as _p3d_err:
               rec['p3_err'] = 'HOOK-D ' + repr(_p3d_err)
           # <<< BAPATCH-P3-HOOK-D v1 END <<<
  +        # >>> BAPATCH-RELAY2-HOOK v1 BEGIN >>>
  +        # 名字已知、但没有真生成器的协议（8000 / 1006 / 8006 / 90011 / 35003 / 16000 …）：
  +        # 开关 cn_relay_known.txt 打开时，把客户端真实请求转发给本地 Shittim
  +        # (/api/gateway)，拿到 dict 回包就用 _cn_envelope 包成 CN 信封返回。
  +        # 挂在这里（`if proto_int:` 之前、同级）等于同时接住两条空壳出口：
  +        #   proto_int 有值 -> 原本走下面的 min-envelope；为 None -> 走 _generic_protocol_response 的 min+base。
  +        # 任何一步不成就原路落回（下面的代码完全不变，绝不 500）。
  +        # 有真生成器的协议号由 RL2_HANDLED 显式排除；Account_CheckNexon(1014) 只由
  +        # ensure_session 内部调用，另有名字级排除 + 同线程重入保护。开关缺失 = 关。
  +        try:
  +            _rl2_a = rl2_route(rec, proto_str, packet_b64, name, self._cn_envelope)
  +            if _rl2_a is not None:
  +                return _rl2_a
  +        except Exception as _rl2_a_err:
  +            rec['relay2_err'] = repr(_rl2_a_err)
  +            rec['relay2_fallthrough'] = 'exception'
  +        # <<< BAPATCH-RELAY2-HOOK v1 END <<<
           if proto_int:
               obj = cn_nick.build_min_response(proto_int)
               rec['fallback'] = 'min-envelope'
  @@ -2822,6 +2839,9 @@
       rec['relay_fallthrough'] = ''
       return out
   # <<< BAPATCH-RELAY-PAYLOAD v1 END <<<
  +# >>> BAPATCH-RELAY2-PAYLOAD v1 BEGIN >>> (deploy/patch_relay2.py 内嵌 RL2_PAYLOAD_SRC，sha256=cab63ac0e9c6e7440d6879dfda56df040385b821c76417ed38945df14532c32d) >>>
  +# ...[232 行运行时模块原样内嵌自 patch_relay2.py 的 RL2_PAYLOAD_SRC，--full-diff 查看]...
  +# <<< BAPATCH-RELAY2-PAYLOAD v1 END <<<
   if __name__ == '__main__':
       n = load_names()
       print('protocol name table =', n, 'entries')

语法检查: PASS
--dry-run：没有写文件。mtime/size 未变: True（(1794852164405428200, 115911)）
           开关文件也没动（正式执行时 --switches keep -> C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\cn_relay_known.txt）
```

### 5.3 `--apply --switches 1`

```text
$ python patch_relay2.py --src _sandbox\p3\account_auth_probe.py --apply --switches 1
已写入。备份: _sandbox\p3\account_auth_probe.py.relay2.bak.20261117-020329
  写入后 128309 字节 / sha256 e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581
  还原命令: cp -a _sandbox\p3\account_auth_probe.py.relay2.bak.20261117-020329 _sandbox\p3\account_auth_probe.py
  （或 python patch_relay2.py --src _sandbox\p3\account_auth_probe.py --rollback）
开关: C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\cn_relay_known.txt=1（新建）

== 打完补丁后的自检 ==
  INFO  src = _sandbox\p3\account_auth_probe.py  (128309 字节 / 3082 行 / sha256 e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581)
  INFO  状态 = 已打补丁（校验补丁后不变量）
  PASS  python 语法检查 compile() 
  PASS  PAYLOAD 标记成对、各 1 处（BEGIN 1 / END 1）
  PASS  HOOK 标记成对、各 1 处（BEGIN 1 / END 1）
  PASS  内嵌 PAYLOAD 逐字节 == patch_relay2.py 的 RL2_PAYLOAD_SRC（sha256 cab63ac0e9c6e744 / cab63ac0e9c6e744）
  PASS  PAYLOAD 标记里记的 sha256 与真源一致（cab63ac0e9c6e744）
  PASS  HOOK 代码块逐字节 == patch_relay2.py 里生成的那份
  PASS  HOOK 整块在 `if proto_int:` 之前（hook@76354 < anchor@77250 == proto_int@77250）
  PASS  HOOK 与 `if proto_int:` 之间没有别的代码（END 标记后面就是锚点）
  PASS  HOOK 起始行缩进 == 8 空格（实测 8）—— 与 `if proto_int:` **同级**
  PASS  HOOK 的 `try:` 缩进 == 8 空格（实测 8）
  PASS  HOOK 体内语句缩进 == 12 空格 == 锚点缩进 + 1 层（实测 12）
  PASS  HOOK 紧跟在 P3-HOOK-D 的 END 标记之后（上一行 = '# <<< BAPATCH-P3-HOOK-D v1 END <<<'）
  PASS  AST：含 rl2_route(...) 的 Try 是 `_bridge` 函数体的一条直接语句（下标 22）
  PASS  AST：它就是 `if proto_int:` 的**直接前一条**语句（hook 下标 22 / proto_int 下标 23）
  PASS  AST：rl2_route 所在 Try 的父节点 == 'FunctionDef'（不是 ExceptHandler/If）
  PASS  反证：把 HOOK 写成 12 空格会掉进 P3-HOOK-D 的 except 处理体（语法=True / 父节点='ExceptHandler'）—— 这正是上一版踩过的坑
  PASS  HOOK 调用了 rl2_route(...) 且注入 self._cn_envelope
  PASS  `if proto_int:` 分支 7 行原样未被改动（min-envelope / _generic_protocol_response）
  PASS  PAYLOAD 在 `if __name__ == '__main__':` 之前（payload@109184 < main@118588）
  PASS  PAYLOAD 排在 relay v1 的 PAYLOAD 之后（relay1@99495 < relay2@109184），rl2_* 运行时才能看到 rl_* 函数
  PASS  既有补丁 BAPATCH-P3-PAYLOAD 仍在（BEGIN 各 1 处，未被动过）
  PASS  既有补丁 BAPATCH-P3-HOOK-E 仍在（BEGIN 各 1 处，未被动过）
  PASS  既有补丁 BAPATCH-P3-HOOK-D 仍在（BEGIN 各 1 处，未被动过）
  PASS  既有补丁 BAPATCH-P3-HOOK-G 仍在（BEGIN 各 1 处，未被动过）
  PASS  既有补丁 BAPATCH-SIMPLE-PAYLOAD 仍在（BEGIN 各 1 处，未被动过）
  PASS  既有补丁 BAPATCH-SIMPLE-HOOK-D 仍在（BEGIN 各 1 处，未被动过）
  PASS  既有补丁 BAPATCH-SIMPLE-HOOK-G 仍在（BEGIN 各 1 处，未被动过）
  PASS  既有补丁 BAPATCH-RELAY-PAYLOAD 仍在（BEGIN 各 1 处，未被动过）
  PASS  既有补丁 BAPATCH-RELAY-HOOK-A 仍在（BEGIN 各 1 处，未被动过）
  PASS  摘掉 PAYLOAD+HOOK 后逐字节 == 基线 115911 B / sha256 377176809ff25949（实测 115911 B / 377176809ff25949）
  PASS  摘块后零 BAPATCH-RELAY2 残留
  PASS  内嵌载荷可 exec
  PASS  转发超时 RL2_TIMEOUT == 8 秒（不是 post_gateway 默认的 40 秒）
  PASS  RL2_HANDLED == 14 个「绝不能被抢」的协议号（实测 14 个：[3, 1000, 1002, 1005, 1009, 1012, 1014, 1017, 1019, 2001, 4000, 24000, 26000, 90004]）
  PASS  RL2_SKIP_NAMES 覆盖 Account_CheckNexon（名字级双保险）
  PASS  开关文件 == cn_relay_known.txt（与 relay v1 的 cn_relay_unknown.txt 独立）
  PASS  开关查找顺序 == bridge 目录 -> /www/wwwroot/bapatch/tools -> /www/wwwroot/bapatch（['C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\server\\deploy', '/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch']）
  PASS  cn_relay_known.txt 缺失 -> 判定「关」（fail-safe）
  PASS  cn_relay_known.txt=1 -> True
  PASS  cn_relay_known.txt=on -> True
  PASS  cn_relay_known.txt=yes -> True
  PASS  cn_relay_known.txt=TRUE -> True
  PASS  cn_relay_known.txt=0 -> False
  PASS  cn_relay_known.txt=空 -> False
  PASS  cn_relay_known.txt=off -> False
  PASS  删除开关文件 -> 又变回「关」
  PASS  rl_read_file 存在时委托给它（复用 relay v1 的查找顺序，不另写一套）
  PASS  委托时文件名 == cn_relay_known.txt（('cn_relay_known.txt', 'C:\\Users\\su\\AppData\\Local\\Temp\\relay2sw_lh8kvlb_')）
  PASS  没有 relay v1 的 rl_request_json/rl_num_from_request -> 落回（fallthrough=no-relay1）
  PASS  开关关：名字已知也照样返回 None（relay2_on=False / fallthrough=switch-off）
  PASS  名字 = Account_CheckNexon -> 不碰（fallthrough=skip-name，双保险）
  PASS  14 个专分支/真生成器协议号一律不抢（fallthrough=handled-N）
  PASS  同线程重入保护：busy=True -> 不接管（fallthrough=reentrant）
  PASS  bridge 四件套缺失 -> 落回（fallthrough=no-deps）
  PASS  没有 cn_cipher.decode_packet -> 落回（fallthrough=no-cn_cipher）
  PASS  decode_packet 抛错 -> 落回 + relay2_err="ValueError('bad packet')"
  PASS  拼不出请求 dict -> 落回（fallthrough=decode-json）
  PASS  取不到协议号 -> 落回（fallthrough=no-protocol-num）
  PASS  开关开 + 全链路替身 -> 返回 _cn_envelope 的 (200, body, ctype)
  PASS  relay2_used=True / relay2_on=True
  PASS  post_gateway 收到 timeout=8（实测 8）
  PASS  发给 Shittim 的请求带 Protocol=8000（8000）
  PASS  SessionKey 缺省时注入（relay2_session_injected=True）
  PASS  relay2_protocol=8000 / relay2_protocol_num=8000
  PASS  relay2_code=200 / relay2_resp_len=78
  PASS  响应经 envelope(协议名, obj, rec) 出口（proto_name='Mission_List', keys=['Echo', 'Protocol']）—— 传名字不传 token
  PASS  成功路径的 7 个日志字段齐备
  PASS  请求里已有 SessionKey -> 不覆盖（relay2_session_injected=False）
  PASS  post_gateway 没有 timeout 形参（TypeError）-> 退回无参调用且只发一次（1 次）
  PASS  ensure_session 回 None（1014 失败）-> 落回，且没有向 Shittim 发请求（0 次）
  PASS  Shittim 回 500 -> 落回 + relay2_err='shittim response not dict (code=500 len=16 body=b\'{"error":"boom"}\')'
  PASS  Shittim 超时（post_gateway 回 code 0）-> 落回 + relay2_err='gateway unreachable/timeout: b\'{"error":"timed out"}\''
  PASS  envelope 没注入 / 返回 None -> 落回（fallthrough=envelope）
自检: 全绿
```

（打完的自检 73 项 PASS / 0 FAIL，"自检: 全绿"。）

### 5.4 回归（必须逐字节 / 逐字段不变）

```text
$ python patch_3.py --src _sandbox\p3\account_auth_probe.py --verify
结论: PASS

$ python _p3_replay.py --target _sandbox\p3\account_auth_probe.py
22 项断言 / 0 FAIL / ALL PASS

$ python _relay_replay.py --target _sandbox\p3\account_auth_probe.py        # 直接对着已打 relay2 的文件
  FAIL  R0   摘掉 PAYLOAD+HOOK-A 后 == 基线 103900 B / 563c1942289968e3（实测 116298 B / 28bb4582f23ffb86）
44 项断言 / 1 FAIL / SOME FAILED

$ python _relay_replay.py --target <115,911 B 基线副本>                        # 去掉 relay2 两块之后
45 项断言 / 0 FAIL / ALL PASS
```

**关于 `_relay_replay.py` 的那个 FAIL（R0，唯一一个）**：它的 R0 把「摘掉 relay v1 两块」的结果
硬编码成 **103,900 B**，而现在文件上多挂了 relay2 的两块，所以摘掉 relay v1 之后是 116,298 B
—— 这是**断言的前提过期**，不是行为回归。证据有两条：

1. 其余 **44 项断言全部 PASS**（R0 之外的所有断言都在这份已打 relay2 的文件上绿了，
   包括 R1「开关关 == legacy」、R2「8000 走 relay v1 的转发管线」、R5「9 个已知协议开关开 vs
   摘掉 relay v1 的 legacy 逐字段一致」、R6「1014 无递归」、R8「重入保护」）；
2. 把**逐字节等于 115,911 B / `377176809f…` 的基线副本**喂给同一个脚本：**45 项 / 0 FAIL / ALL PASS**。

本次**没有**去改 `_relay_replay.py`（已验证资产，不动）；下次如果要让它在「叠加了 relay2」的文件上
也全绿，只需把 R0 的期望值换成 `P.BASE_SIZE` 参数化。

### 5.5 新功能取证：`_relay2_replay.py`（62 项）

```text
$ python _relay2_replay.py --target _sandbox\p3\account_auth_probe.py
target : _sandbox\p3\account_auth_probe.py
         128309 字节 / sha256 e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581
patched: 是

== 重放断言 ==
  PASS  S0   摘掉 PAYLOAD+HOOK 后 == 基线 115911 B / 377176809ff25949（实测 115911 B / 377176809ff25949）
  PASS  S0   HOOK 整块在 `if proto_int:` 之前（hook@76354 < proto_int@77250）
  PASS  S0   HOOK 与 `if proto_int:` 同为 8 空格缩进（实测 8 / 8）
  PASS  S0   AST：HOOK 是 `_bridge` 里 `if proto_int:` 的直接前一条语句（下标 22 / 23，父节点 'FunctionDef'）
  PASS  S0   基线里零 BAPATCH-RELAY2 残留
  INFO  S0   模拟线上名字表：给 3 个装置各补 9 条名字（本机没有 protocol_names.txt）—— ['Mission_GuideMissionSeasonList', 'Shop_ListTutorialGacha', 'MiniGame_MissionList', 'Toast_List']
  PASS  S0   三个装置的名字表补丁一致（9 / 9 / 9）
  PASS  S0   8000 的 token 在名字表里（= 'Mission_List'）—— 与线上一样，name is not None
  PASS  S1   开关关：8000 -> 200 / gen_kind='min+base'（min+base 空壳，300 B）
  PASS  S1   开关关：relay2_on=False / fallthrough='switch-off' / relay2_used 不存在
  PASS  S1   开关关：内层仍是假壳 Protocol=8000（键=['BattlePassMissionProgressDBDict', 'EventMissionProgressDBDict', 'MissionProgressDBs', 'Protocol', 'ServerNotification', 'ServerTimeTicks', 'StaticOpenConditions']）
  PASS  S1   开关关：假 Shittim 一次都没被调用（0 次）
  PASS  S1   开关关：响应与摘掉本补丁的现状逐字段一致（掩 tick 后；gen_kind='min+base'）
  PASS  S2   开关开：8000 -> 200，relay2_used=True / relay2_on=True
  PASS  S2   relay2_protocol=8000 / relay2_protocol_num=8000（= Hash>>32）
  PASS  S2   内层是假 Shittim 的真响应（Protocol=8000 / Echo=['AccountId', 'Hash', 'IsTest', 'Protocol']）
  PASS  S2   relay2_code=200 / relay2_resp_len=108
  PASS  S2   SessionKey 由 ensure_session(1014) 注入（relay2_session_injected=True / relay2_err=''）
  PASS  S2   假 Shittim 收到 1014=1 次 / 8000=1 次（先铸会话再转发，各一次）
  PASS  S2   转发请求里的 SessionKey == Shittim 铸的那张（AccountServerId=2 / MxToken 64 字符）
  PASS  S2   post_gateway 收到 timeout=8（不是默认 40；实测 [8]）
  PASS  S2   外层 protocol == 客户端自己的 token（'5S4LD3Y34GQ2GPKJ75FIIFQWCQ'）—— 客户端看不出中间换了数据源
  PASS  S2   开关开后的内层 != 开关关时的 min+base 空壳（真的换了数据源）
  PASS  S7   成功路径的 7 个日志字段齐备
  PASS  S2b  proto_int 有值 + 开关关：走 `if proto_int:` 的 min-envelope（fallback='min-envelope' / 109 B）
  PASS  S2b  proto_int 有值 + 开关开：仍被 relay2 接住（relay2_used=True / fallthrough=''）—— 证明钩子确实在 `if proto_int:` 之前
  PASS  S3   1006 Account_SetTutorial              -> Shittim 真响应（relay2_protocol=1006 / 内层 Protocol=1006）
  PASS  S3   1006 开关关 -> 仍是空壳（gen_kind='min+base'），与开关开的数据不同
  PASS  S3   8006 Mission_GuideMissionSeasonList   -> Shittim 真响应（relay2_protocol=8006 / 内层 Protocol=8006）
  PASS  S3   8006 开关关 -> 仍是空壳（gen_kind='min+base'），与开关开的数据不同
  PASS  S3   90011 Shop_ListTutorialGacha           -> Shittim 真响应（relay2_protocol=90011 / 内层 Protocol=90011）
  PASS  S3   90011 开关关 -> 仍是空壳（gen_kind='min+base'），与开关开的数据不同
  PASS  S3   35003 MiniGame_MissionList             -> Shittim 真响应（relay2_protocol=35003 / 内层 Protocol=35003）
  PASS  S3   35003 开关关 -> 仍是空壳（gen_kind='min+base'），与开关开的数据不同
  PASS  S3   16000 Toast_List                       -> Shittim 真响应（relay2_protocol=16000 / 内层 Protocol=16000）
  PASS  S3   16000 开关关 -> 仍是空壳（gen_kind='min+base'），与开关开的数据不同
  PASS  S3   19003 Scenario_Skip                    -> Shittim 真响应（relay2_protocol=19003 / 内层 Protocol=19003）
  PASS  S3   19003 开关关 -> 仍是空壳（gen_kind='min+base'），与开关开的数据不同
  PASS  S3   19004 Scenario_Select                  -> Shittim 真响应（relay2_protocol=19004 / 内层 Protocol=19004）
  PASS  S3   19004 开关关 -> 仍是空壳（gen_kind='min+base'），与开关开的数据不同
  PASS  S3   25003 Event_RewardIncrease             -> Shittim 真响应（relay2_protocol=25003 / 内层 Protocol=25003）
  PASS  S3   25003 开关关 -> 仍是空壳（gen_kind='min+base'），与开关开的数据不同
  PASS  S3   15002 OpenCondition_EventList          -> Shittim 真响应（relay2_protocol=15002 / 内层 Protocol=15002）
  PASS  S3   15002 开关关 -> 仍是空壳（gen_kind='min+base'），与开关开的数据不同
  PASS  S3   36001 Notification_EventContentReddotC -> Shittim 真响应（relay2_protocol=36001 / 内层 Protocol=36001）
  PASS  S3   36001 开关关 -> 仍是空壳（gen_kind='min+base'），与开关开的数据不同
  PASS  S4   Shittim 回 500 -> bridge 仍 200 / gen_kind='min+base' / relay2_err='shittim response not dict (code=500 len=36 body=b\'{"error":"injected-shittim-failure"}\')'
  PASS  S4   落回的内层是 min+base 空壳（Protocol=8000 / relay2_code=500）
  PASS  S4   Shittim 回 200 非 JSON -> 仍 200 / fallthrough='shittim-non-dict'
  PASS  S4   Shittim 超时 -> 仍 200 / gen_kind='min+base' / relay2_err='gateway unreachable/timeout: b\'{"error":\\\'timed out\\\'}\''（2.0 s 内返回）
  PASS  S4   post_gateway 抛异常 -> 仍 200 / fallthrough='exception' / relay2_err 非空
  PASS  S6   Account_CheckNexon(1014) -> 200 / 内层 Protocol=1014 / 只调用 1 次（0.02 s）
  PASS  S6   1014 的 rec 里没有任何 relay2_* 字段（[]）—— 钩子根本没碰它，无递归
  PASS  S5   Account_Auth(1002)：开关开 / 开关关 / 打补丁前 三者响应逐字段一致（gen_kind=None / relay2_used 不存在 / fallthrough=None / 现状自证可复现=True）
  INFO  S5     ↳ Account_Auth(1002) rec relay2_* = []
  PASS  S5   Account_CheckNexon(1014)：开关开 / 开关关 / 打补丁前 三者响应逐字段一致（gen_kind=None / relay2_used 不存在 / fallthrough=None / 现状自证可复现=True）
  INFO  S5     ↳ Account_CheckNexon(1014) rec relay2_* = []
  PASS  S5   Academy_GetInfo(24000)：开关开 / 开关关 / 打补丁前 三者响应逐字段一致（gen_kind='academy-24000-v3' / relay2_used 不存在 / fallthrough=None / 现状自证可复现=True / 字节仅差 tick-uuid）
  INFO  S5     ↳ Academy_GetInfo(24000) rec relay2_* = []
  PASS  S5   Account_LoginSync(1017)：开关开 / 开关关 / 打补丁前 三者响应逐字段一致（gen_kind='loginsync-1017-dynamic' / relay2_used 不存在 / fallthrough='skip-name' / 现状自证可复现=True / 字节仅差 tick-uuid）
  INFO  S5     ↳ Account_LoginSync(1017) rec relay2_* = ['relay2_err', 'relay2_fallthrough', 'relay2_on']
  PASS  S5   Item_List(4000)：开关开 / 开关关 / 打补丁前 三者响应逐字段一致（gen_kind='simple-4000' / relay2_used 不存在 / fallthrough=None / 现状自证可复现=True / 字节仅差 tick-uuid）
  INFO  S5     ↳ Item_List(4000) rec relay2_* = []
  PASS  S5   Account_GetTutorial(1005)：开关开 / 开关关 / 打补丁前 三者响应逐字段一致（gen_kind='simple-1005' / relay2_used 不存在 / fallthrough='handled-1005' / 现状自证可复现=True / 字节仅差 tick-uuid）
  INFO  S5     ↳ Account_GetTutorial(1005) rec relay2_* = ['relay2_err', 'relay2_fallthrough', 'relay2_name', 'relay2_num', 'relay2_on']
  PASS  S5   Content_SaveGet(26000)：开关开 / 开关关 / 打补丁前 三者响应逐字段一致（gen_kind='simple-26000' / relay2_used 不存在 / fallthrough=None / 现状自证可复现=True / 字节仅差 tick-uuid）
  INFO  S5     ↳ Content_SaveGet(26000) rec relay2_* = []
  PASS  S5   NetworkTime_Sync(3)：开关开 / 开关关 / 打补丁前 三者响应逐字段一致（gen_kind='networktime-3' / relay2_used 不存在 / fallthrough=None / 现状自证可复现=True / 字节仅差 tick-uuid）
  INFO  S5     ↳ NetworkTime_Sync(3) rec relay2_* = []
  PASS  S5   Management_Data(90004)：开关开 / 开关关 / 打补丁前 三者响应逐字段一致（gen_kind='management-90004' / relay2_used 不存在 / fallthrough=None / 现状自证可复现=True / 字节仅差 tick-uuid）
  INFO  S5     ↳ Management_Data(90004) rec relay2_* = []
  INFO  S5   9 个已知协议里 2 个原始字节完全相同，其余仅差 ServerTimeTicks/uuid/时间字符串（掩码后全部逐字段一致；打补丁前自身两次运行也在同一批字段上不同）
  PASS  S8   全程只监听 127.0.0.1:56955（假 Shittim），未连任何远端

62 项断言 / 0 FAIL / ALL PASS
```

覆盖的任务要求（逐条对号）：

| 要求 | 断言 |
|---|---|
| 开关关：8000 仍是 `min+base` 空壳，假 Shittim 0 次 | S1（5 条；本地替身没有 AES，所以是 300 B，线上是 536 B，结构一致） |
| 开关开：8000 拿假 Shittim 的真响应，`relay2_used=True` | S2（10 条，含 `timeout=8`、SessionKey 注入、外层 protocol == 客户端 token） |
| 强制 `proto_int` 有值（模拟线上 `req_Hash` 已置）也照样接管 | S2b（2 条：关=min-envelope / 开=relay2） |
| 1006/8006/90011/35003/16000/19003/19004/25003/15002/36001 都走 relay2 | S3（20 条：每协议 2 条，开=真数据 / 关=空壳） |
| 假 Shittim 500 / 200 非 JSON / 超时 / post 抛异常 → 200 + `min+base` + `relay2_err` | S4（5 条） |
| 1002/1014/24000/1017/4000/1005/26000/3/90004 开关开着时 `relay2_used` 不存在且响应逐字段一致 | S5（9 条，三方对照：开关开 / 开关关 / 打补丁前） |
| Account_CheckNexon 不被钩子拦（无递归） | S6（2 条：只 1 次 1014、rec 里零 `relay2_*`） |
| 日志字段齐备 | S7（1 条） |
| 只监听 127.0.0.1 | S8（1 条） |
| **合计** | **S0 7 + S1 5 + S2 10 + S2b 2 + S3 20 + S4 5 + S5 9 + S6 2 + S7 1 + S8 1 = 62 项 / 0 FAIL** |

### 5.6 `--rollback`（精确回到 377176809f…，零残留）

```text
$ python patch_relay2.py --src _sandbox\p3\account_auth_probe.py --rollback
src     : _sandbox\p3\account_auth_probe.py
          128309 字节 / 3082 行 / sha256 e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581
patched : 是
已用备份还原: C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_sandbox\p3\account_auth_probe.py.relay2.bak.20261117-020329
  还原后 115911 字节 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
  残留 BAPATCH-RELAY2 标记: 无（干净）
```

回滚后再跑一次 `--verify`（应回到「未打补丁 / 基线」分支）：

```text
$ python patch_relay2.py --src _sandbox\p3\account_auth_probe.py --verify
src     : _sandbox\p3\account_auth_probe.py
          115911 字节 / 2831 行 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
patched : 否
  ...（18 项 PASS / 0 FAIL，同 §5.1）
结论: PASS
```

最终沙箱状态：

```
115,911 B / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
```

---

## 6. 回滚命令 / 上线 / 关闭

### 6.1 回滚（线上）

```bash
# 优先用备份还原（脚本会挑 sha == 377176809f… 的那个 .relay2.bak.*）
python3 /www/wwwroot/bapatch/patch_relay2.py \
    --src /www/wwwroot/bapatch/tools/account_auth_probe.py --rollback

# 没有可用备份时直接摘块（结果逐字节相同，--verify 每次都在证明这一点）
python3 /www/wwwroot/bapatch/patch_relay2.py \
    --src /www/wwwroot/bapatch/tools/account_auth_probe.py --rollback --from-block-removal
```

回滚后**必须重启 bridge**（脚本只改文件，不重载进程）。

### 6.2 关闭功能（不重启）

```bash
echo 0 > /www/wwwroot/bapatch/cn_relay_known.txt      # 或直接 rm
```

开关每个请求都读一次（与 `cn_3.txt` / `cn_1005.txt` 同款），缺失/0 → 完全不接管。

### 6.3 上线步骤

```bash
python3 patch_relay2.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --verify   # 必须先 PASS
python3 patch_relay2.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --apply --switches 1
# 重启 bridge（历史 pid 2569402；重启会踢掉在线客户端 → 等用户退出再重启）
```

**顺序红线**：relay2 复用 relay v1 的 `RL_PAYLOAD`。回滚时**必须先 relay2、后 relay1**；
反过来会让 relay2 以 `relay2_fallthrough='no-relay1'` 落回（fail-safe：不 500、只是功能失效）。

---

## 7. 「开关打开后 8000 会拿到 Shittim 真数据」的信心依据

1. **分支真的可达**：重放里直接用 bridge 的 `Handler._bridge()`（不是模拟分发），
   开关开 → S2/S3 拿到假 Shittim 的 `Echo` 真响应；开关关 → S1/S3 仍是 `min+base` 且假 Shittim
   **0 次调用**。同一个文件、同一个请求，只差一个开关文件。
2. **请求真的发出去了**：假 Shittim 侧记录到 `1014` 恰好 1 次（铸会话）、`Protocol=8000` 恰好 1 次，
   且 8000 那个请求里带着刚铸的 `SessionKey = {"AccountServerId":2,"MxToken":<64>}`（S2）。
3. **超时真的是 8 秒**：重放把 `post_gateway` 包了一层记录实参，实测收到 `timeout=8`（S2），
   不是默认 40；`post_gateway` 没有 timeout 形参的变体 bridge 会退回无参调用且只发一次（自检）。
4. **失败一定落回，不 500**：500 / 200 非 JSON / 超时（2 s 内返回）/ `post_gateway` 抛异常
   四种故障全部 200 + `min+base` + `relay2_err` 非空（S4）。
5. **已知协议一个没动**：9 个协议三方对照（开关开 / 开关关 / 打补丁前）逐字段一致（S5），
   外加 relay1 的 45 项、p3 的 22 项回归全绿（§5.4）。
6. **线上口径对齐**：`_cn_envelope` 收的是**协议名**（它内部算 `base32(md5(名字))`，正好等于
   客户端请求里带的 token）—— 和 bridge 自己的 path A 完全同一个调法；S2 断言了
   「外层 protocol == 客户端自己的 token」。
7. **剩下的不确定性**（如实说明）：沙箱这份 bridge 比线上旧一版（相差 ~2.3 KB），
   如果线上那份的 `_cn_envelope` 签名不同，relay2 会抛异常 → 落回 `min+base`
   （日志里 `relay2_fallthrough='exception'` + `relay2_err`），**不会 500 但功能不生效**。
   所以上线后第一件事是 grep 日志：`relay2_used=True` / `relay2_resp_len` 应在 800 左右
   （Shittim 实测 804 B），而不是 `min+base` 的 536 B。

---

## 8. 发现 · 风险 · 遗留

1. **`relay2` 不该传 token 给 `_cn_envelope`（本次的设计决定）**：`_cn_envelope(proto_name, …)`
   内部会 `base32(md5(proto_name))`，客户端请求里的 protocol 字段正是 `base32(md5(协议名))`。
   所以必须传**协议名**，传 token 会得到 `b32(md5(b32(md5(name))))`，外层 protocol 就和客户端对不上。
   relay2 已按「传名字」实现并断言；relay v1 的 HOOK-A 传的是 `proto_str`（token）—— 那条分支只有
   `name is None` 的协议，本来就没有名字可用，属于既有实现，本次**没有改动**，仅在此记录口径差异。
2. **`_relay_replay.py` R0 的前提过期**（详见 §5.4）：建议下次把它参数化，本次不动已验证资产。
3. **本地替身没有 AES**：`cn_cipher` / `cn_wire` 用长度、容器、信封逐字段等价的替身，
   所以 `min+base` 本地是 300 B、线上是 536 B；**看 `gen_kind` 与键集合，不看字节数**（与
   `FALLBACK_QUEUE_20261117.md` 的验收口径一致）。
4. **本地没有 `protocol_names.txt`**：重放里给 3 个装置的 `NAME_TABLE` 各补 9 条名字，模拟线上
   202 条名字表（线上文件存在，不需要这一步）；`Account_SetTutorial` / `Mission_List` 本地
   `BUILTIN_NAMES` 里本来就有。
5. **开关是全量的**：`cn_relay_known.txt` 打开后，所有「名字已知但没生成器」的协议都会发给 Shittim。
   如果某个协议 Shittim 没有 handler，会落回 `min+base`（日志 `relay2_fallthrough` 可统计），
   行为不劣于现在，但会多一次本地 HTTP（≤8 s）。要谨慎可先只观察 8000 的 `relay2_resp_len`。
6. **首次请求可能慢**：`ensure_session()` 冷启动要打 1014（内部用 `post_gateway` 默认 40 s 超时），
   与 relay v1 相同；之后走 `SESSION` 缓存，只有转发那一步是 8 s。
7. **一条实测更正**：`proto_int` 在本仓库副本里几乎恒为 `None`（`req_Hash` 只在 path A 解出
   json dict 时才赋值），线上 `gen_kind=min+base` 也说明 8000 走的是 `_generic_protocol_response`。
   钩子放在 `if proto_int:` 之前**同时**罩住两条出口；S2b 另外用 `rec_extra={'req_Hash': 8000<<32}`
   强制 `proto_int` 有值，证明出口 ① 也被罩住。

---

## 9. 文件清单与指纹

| 文件 | 字节 | sha256 |
|---|---|---|
| `work/ba/server/deploy/patch_relay2.py` | 67,677 | `32e54a3cb126d6ddbd4295ba4b1cac64251181b221132a5ecaec58cdbee607b3` |
| `work/ba/server/deploy/_relay2_replay.py` | 41,039 | `30e43a5e627fc6896efb40766b8a1f86741942523348271ae0bd7fed89a4c6d1` |
| `work/ba/server/deploy/PROGRESS_RELAY2.md` | 本文件 | — |
| 沙箱基线 `_sandbox/p3/account_auth_probe.py` | 115,911 | `377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07` |
| 打完 relay2 的沙箱文件 | 128,309 | `e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581` |

**本次没有改动**（仅供核对，sha 与接手时一致）：

| 文件 | 字节 | sha256 |
|---|---|---|
| `patch_relay.py` | 54,297 | `3fe9a1687d5d2c091646be5758eecdd1f8cef59bfbc6b490f8bc000fa414c197` |
| `_relay_replay.py` | 38,134 | `ce55d10ef4b20313c242a8dd692dd47df9c091d99a8e6464d9171baff0b2aff2` |
| `patch_3.py` | 63,870 | `09584f25fc93777ae795eb2acf6f40e3a2af4cebf9988b3a2506b978ea1f7ef4` |
| `_p3_replay.py` | 12,541 | `65946b813d8d46c1866a4dde8ef0bdb8ee42023cc2c80f10a604538599100556` |

命令速查：

```bash
python patch_relay2.py --src <file> --verify                  # 基线指纹 + 锚点 + 缩进/AST + 载荷单测
python patch_relay2.py --src <file> --dry-run                 # 只看插入位置与 diff（不写文件）
python patch_relay2.py --src <file> --apply --switches 1      # 打补丁 + 开开关 + 自检
python patch_relay2.py --src <file> --rollback                # 还原到 377176809f…
python _relay2_replay.py --target <file>                      # 62 项本地重放
```

