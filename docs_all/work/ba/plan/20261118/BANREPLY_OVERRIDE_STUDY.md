# BANREPLY OVERRIDE STUDY —— 封禁包被覆盖 + DevId 解析失败：缺陷定位与修复方案

> 轮次：2026-11-18 20:39 起 ｜ 目标：`work/ba/server/deploy/_build_banreply/account_auth_probe.py`
> 性质：**只定位 + 出方案**，本轮未修改任何既有文件，未产出改好的 `.py`。
> 产物：`work/ba/plan/20261118/BANREPLY_OVERRIDE_STUDY.md`（本文）+
> `work/ba/plan/20261118/_banreply_bug/_len_probe.py` / `_len_probe_out.txt`（只读长度探针，不是补丁）。
> 基线 md5 未变（215feddd…），`_build_banreply/` 下文件一字未动。

---

## §0 基线校验（先做，已完成）

```
文件   work\ba\server\deploy\_build_banreply\account_auth_probe.py
md5    215feddd3ecf281cd61273149b89fd91     ← 与要求一致
size   207148 B                            ← 与要求一致
lines  5008                                ← 与要求一致（ReadAllLines=5008，LF=5008，CRLF=0）
```

校验命令与结果（本机实测）：

```powershell
$p="work\ba\server\deploy\_build_banreply\account_auth_probe.py"
(Get-FileHash $p -Algorithm MD5).Hash.ToLower()          # 215feddd3ecf281cd61273149b89fd91
(Get-Item $p).Length                                      # 207148
[System.IO.File]::ReadAllLines($p).Length                 # 5008
```

`MD5.txt` 记的也正是这一份（0718 那行：`215feddd…  207148 B   5008 行`），基线 = `_build_banexp/account_auth_probe.py`（191670 B）。**基线相符，下面的行号全部是对这一份的。**

> 注：`Get-Content | Measure-Object -Line` 会报 4198（空行计数口径问题），不要用那个口径判断行数。

---

## §1 现象复述与日志证据

### 1.1 现场数据（真机 20:36–20:37）

| 时刻 | 日志 | 含义 |
|---|---|---|
| 20:36:07 | `banreply=hit reason='永久' acct_id_src=retarget-fallback acct_server_id=10000000005 resp_len=3500` | 封禁判定命中，但 `_req_dict` 没拿到 DevId，退兜底号 |
| 20:37:24 | `banreply=hit reason='永久' acct_id_src=exact acct_server_id=10000000005 resp_len=3500` | 同一个号，`acct_id_src` 变了但 `req_devid_src` 仍是 `fallback` |
| 20:29:08 | `acct_id_src=exact server=10000000003 pub=854071516 pub_src=devid req_devid_src=（正常）` | **这是 path A（`decrypt+`）在跑**的时期，DevId 正常 |

落盘明文 `/www/wwwroot/_ba_state/round18_A_plain.txt`（mtime 20:37）：
`outer.keys = ['protocol','packet','requestid']`，`inner` 33 键，`Protocol=1002`，`AccountDB.ServerId=10000000005`，`Nickname='老师0006'`，**无 `ErrorCode`、无 `BanReason`**。

`acct_svc.log` 里 `[banreply]` 条目数 = 0。

### 1.2 三处证据的读法（关键，先纠正一个前提）

**证据 A：`round18_A_plain.txt` 的内容是"决定性的"，`resp_len` 只是旁证。**

`Protocol = 1002` 并且是 **int**、33 键、含 `AccountLimitedFlashSaleDBs` —— 全文件里只有一处能产出这种内层：

- `cn_inner27.build(1002)` → `work/ba/server/deploy/_baseline/cn_inner27.py:41-128`
  `d = {"Protocol": protocol_value}`（`:42`，int）+ 27 个声明字段（`:26-34`）+ `SessionKey/ServerTimeTicks/...`（`:100-110`）
- 再加 `acct_apply_to_auth` 换掉 `AccountDB` / `SessionKey`（`account_auth_probe.py:177-178`）→ 33 键、`ServerId` 取自 accounts.db、`Nickname` 取自库

而这**两个函数正是 `_cn_enc_b64` 的 `a_proto_int` 分支的唯一内容**（`:3023-3024`）。封禁包的内层是 4 键（`banreply_build:1911-1914`：`Protocol/ServerTimeTicks/ErrorCode/BanReason`），**不可能**变成这条路。

`resp_len=3500` 的旁证（本机纯长度算术复现，见 `_len_probe_out.txt`）：

| | 内层 | 容器 | 期望 resp_len |
|---|---|---|---|
| 封禁包 | 4 键 | `cn_wire` | **≈ 300 B** |
| `a_proto_int` 重建的 Account_Auth | 32 键（本机 `StaticOpenConditions={}`，是下界） | `cn_wire` | **≈ 2136 B**，补上线上 `StaticOpenConditions`（≈1 KB）后落在 3500 |
| 线上实测 | 33 键 | — | **3500** |

反解：`resp_len=3500` 需要 outer 明文 2576–2591 B；本机 A 组 1561 B，缺口 1015–1030 B 正好是 `cn_inner27.py:103-108` 从 `/www/wwwroot/_ba_state/e1_inner.json` 读 `StaticOpenConditions` 的那一块（本机无此文件，所以只给下界）。**3500 B 离封禁包（300 B）差 3200 B，不可能是封禁包。**

**证据 B：`banreply=hit` 只证明"命中了"，不证明"用了它的返回值"。**

`rec['banreply'] = 'hit'` 写在 `banreply_response:1950`，**在编码之前**。所以它存在不能区分：
- (i) 封禁包的返回值被 `_bridge:3256` 正常 return、只是内容已被替换；
- (ii) 封禁包编码抛异常后被 `:1963` 吞掉、`_bridge` 继续走到 path B。

两种情形**发出去的字节完全相同**（都是 3500 B 的 Account_Auth）。区分方法见 §6.2。

**证据 C：`[banreply]` 日志 0 条。**

`acct_log`（`:59-64`）内部 `try/except: pass`，写失败静默。`[banreply]` 那两句（`:1956` 正常、`:1967` 异常）都在 `try` 里且外层还有兜底 —— **它没落盘说明 `acct_log` 这条路本身写不进去，不能反推"没执行到"**。判定"命中"要用 `rec['banreply']=='hit'`（已在日志里），不要用 `acct_svc.log`。

---

## §2 两个出口的调用顺序图（含行号）

### 2.1 一句话结论

**同一个请求里，封禁包先出、但它的"内层对象"在编码器里被换掉了；返回动作没有丢失。**
`_bridge:3256` 确实 return 了封禁包的返回值 —— 丢的不是 `return`，是 `inner_obj`（`_cn_enc_b64:3023`）。

### 2.2 时间线（自上而下 = 执行顺序，全部 `account_auth_probe.py`）

```
_handle                        :2753
 ├ _read_request_body          :2755
 ├ rec = {...}                 :2763
 ├ code, resp, ctype = self._bridge(body, rec)      :2775   ← 唯一入口
 │
 └─ _bridge                    :3227
     ├ parse_cn_multipart      :3228      -> protocol / packet
     ├ name = name_fix_resolve :3244      -> 'Account_Auth'
     │
     ├ 【出口① 封禁】BAPATCH-BANREPLY v1 Hook           :3245-3259
     │   ├ _br = banreply_response(self, rec, name, packet_b64, proto_str)   :3254
     │   ├ if _br is not None: return _br                                    :3255-3256   ← 这里的 return 是好的
     │   └ except: rec['banreply_err'] = ...                                 :3257-3258
     │
     ├ billing_block_response  :3261-3263     （未命中则 None）
     ├ dedup_replay            :3266-3268
     ├ p3 HOOK-E               :3276-3285
     ├ if exp == 'experror'    :3287-3293
     ├ if name is None: ...    :3295-3319     （name 已是 'Account_Auth'，不进）
     │
     ├ -------- path A: want_decrypt = exp.startswith('decrypt+')  :3321
     │   └ if want_decrypt and packet_b64:                          :3324
     │       ├ cn_cipher.decode_packet                             :3326
     │       ├ _FRAG_TLS.v = r['fragment'] ; .seq = id(rec)        :3337-3338  ← _FRAG_TLS 唯一主写入点
     │       ├ rec['req_frag_head'] = mask_secret(...)             :3346      ← 脱敏！不可再解析
     │       ├ ensure_session / post_gateway                       :3351 / 3358
     │       └ if cn_resp_format()=='cn_envelope':
     │           └ _cn_envelope(name, obj, rec)                    :3368      ← 出口② 的一个调用点
     │
     ├ -------- path B: 合成                       :3374
     │   ├ name == 'Account_CheckNexon'            :3375-3380
     │   └ name in ('Account_Auth','Account_Auth2') :3381
     │       ├ ensure_session                      :3382
     │       ├ post_gateway                        :3387
     │       ├ if cn_resp_format()=='cn_envelope':
     │       │   └ _cn_envelope('Account_Auth', obj, rec)   :3396     ← 出口② 的另一个调用点
     │       └ else _json_ok / resultstate         :3397-3399
     │
     ├ path C0/CallName / path C/Nickname          :3400-3437  （都走 _cn_send_envelope，第五键出口）
     └ path D: simple/p3/relay2/min-envelope/generic :3439-3499
```

### 2.3 两个"出口"的真身

| | 出口① 封禁 | 出口② Account_Auth 正常出口 |
|---|---|---|
| 函数 | `banreply_response` `:1920-1970` | path A `:3368` / path B `:3396` |
| 内层构造 | `banreply_build` `:1895-1917`（4 键，`:1911-1914`） | Shittim 网关回包 `obj`，或 `cn_inner27.build` |
| 终端编码 | `cn_resp_format()=='cn_envelope'` → `handler._cn_envelope('Error', inner, rec)` `:1960-1961`<br>否则 → `handler._json_ok('Error', inner)` `:1962` | `_cn_envelope(name, obj, rec)` `:3368` / `:3396` |
| 共同下游 | **`_cn_envelope` `:2812`** | **同一个 `_cn_envelope` `:2812`** |

**两条出口在同一个函数汇合**：`_cn_envelope:2812`

```
_cn_envelope                       :2812
 ├ inner_obj = apply_field_patch(inner_obj, rec)     :2813
 ├ inner_obj = apply_flatten(inner_obj, rec)         :2814
 ├ if cn_wrap_mode() in ('cn_enc_b64','cn_enc_b64_probe','real_captured',…,'a_proto_int','b_proto_str'):  :2815
 │   └ return self._cn_enc_b64(proto_name, inner_obj, rec)   :2816   ← 线上经此（11 个模式的宽闸门）
 ├ if cn_proto_val()=='name': ...                    :2817-2822
 ├ wire = cn_cipher.wrap_packet(payload)             :2829
 └ return 200, json.dumps(out)                       :2850-2851
```

```
_cn_enc_b64                        :3019
 ├ import uuid                       :3020
 ├ if cn_wrap_mode() in ('a_proto_int','b_proto_str'):     :3021     ★ 线上命中
 │   ├ pv = 1002 if 'a_proto_int' else 'Account_Auth'      :3022     ★ int 1002
 │   ├ inner = cn_inner27.build(pv)                        :3023     ★★★ inner_obj 在这里被扔掉
 │   ├ inner = acct_apply_to_auth(inner, rec)              :3024     ★ 换 AccountDB/SessionKey
 │   ├ rid = str(_uuid.uuid4())                            :3025
 │   ├ wire, plain, key = cn_wire.wrap_response('Account_Auth', inner, rid)   :3026  ★ 协议名写死
 │   ├ rec['wrap_mode'] / 'enc_*' / 'canary_skipped'        :3027-3034
 │   ├ rec['_send_opts'] = {'ctype':'text/plain...','close':True}  :3035
 │   ├ dump round18_A_wire.bin / round18_A_plain.txt       :3036-3042  ★ 就是那个 mtime 20:37 的文件
 │   └ return 200, wire, 'text/plain; charset=utf-8'       :3043
 ├ if cn_wrap_mode()=='e4_strict_dto': ...            :3044-3067
 ├ ... 其它实验模式 ...                                :3068-3176
 ├ inner = dict(inner_obj)        ← 只有非实验模式才"尊重传入对象"   :3178
 └ wire = cn_wire.wrap_response(proto_name, inner, rid)             :3186
```

### 2.4 同一次请求的实际顺序（线上配置 `cn_resp_format=cn_envelope` + `cn_wrap_mode=a_proto_int`）

```
:2775 _handle -> _bridge
:3254 banreply_response
        :1931 name in CN_BANREPLY_PROTO          -> True (Account_Auth)
        :1933 banreply_on()                      -> True
        :1937 _acct_frag_text(rec)               -> ''  （path B，_FRAG_TLS 空）
        :1942 handler._cn_decode_any(packet)     -> 真 fragment  ★ 封禁侧自己解包，所以能拿到真身份
        :1945 banreply_build                     -> pub=854071516, inner={...,'ErrorCode':1025,'BanReason':'永久'}
        :1950 rec['banreply']='hit'              ★ 标记在这里落下（这就是日志里那行）
        :1956 acct_log('[banreply] ...')         -> 静默失败（见 §1.2-C）
        :1961 handler._cn_envelope('Error', inner, rec)
                :2813 apply_field_patch          -> 给封禁包加了 10 个 AccountAuthResponse 键（后被丢弃）
                :2814 apply_flatten              -> SessionKey 不是 dict，原样返回
                :2815 cn_wrap_mode()=='a_proto_int' -> True
                :2816 _cn_enc_b64('Error', inner, rec)
                        :3021 命中 a_proto_int
                        :3023 inner = cn_inner27.build(1002)     ★★★ 封禁 inner 在此丢失
                        :3024 acct_apply_to_auth -> _req_dict -> _FRAG_TLS 空 -> 'fallback' -> 兜底号
                        :3026 wrap_response('Account_Auth', ...)  ★ 外层协议名也从 'Error' 变成 'Account_Auth'
                        :3039 落盘 round18_A_plain.txt（33 键 / Protocol=1002 / 无 BanReason）
                        :3043 return 200, wire(3500B), text/plain
        :1961 返回给 banreply_response -> :1962 不执行
:3254 _br = (200, 3500B, text/plain)  —— 非 None
:3255-3256 return _br                       ★ 返回值**被用了**，没有被后面覆盖
:2775 code, resp, ctype = (200, 3500B, text/plain)
:2793 rec['resp_len'] = 3500
:2796 self._log(rec)                        -> 日志里 banreply=hit + resp_len=3500 同时出现
:2797 self._send(200, resp=3500B)           -> 客户端收到"正常登录包"
```

---

## §3 覆盖的确切位置与原因

### 3.1 确切位置

| 项 | 值 |
|---|---|
| **文件** | `work/ba/server/deploy/_build_banreply/account_auth_probe.py` |
| **覆盖行** | **`:3023`** `inner = cn_inner27.build(pv)` |
| **闸门行** | **`:3021`** `if cn_wrap_mode() in ('a_proto_int', 'b_proto_str'):` |
| **触发开关** | `/www/wwwroot/bapatch/cn_wrap_mode.txt` 内容 = `a_proto_int` |
| **调用链** | `_bridge:3254` → `banreply_response:1961` → `_cn_envelope:2815-2816` → `_cn_enc_b64:3021-3023` |
| **一句原因** | `_cn_enc_b64` 的 `a_proto_int` 分支**完全忽略入参 `inner_obj` / `proto_name`**，无条件重建一份 `Account_Auth(1002)`；封禁包的内层对象在这里被丢弃，外层协议名也被硬写成 `'Account_Auth'`（`:3026`）。 |

### 3.2 为什么"后者的返回值把前者丢了"这个描述需要修正

`_bridge:3255-3256` 的 `if _br is not None: return _br` **是有效的**，封禁包的返回值确实是最终返回值（`_handle:2775` 收下、`:2797` 发出去）。
所以：

- ❌ 不是"被封禁包的返回值被后续路径覆盖"；
- ✅ 是"封禁包的**内容**在它自己的编码器里被换成了 Account_Auth"。

这决定了修法：**"命中后立刻 return" 是无效修复**（`:3256` 本来就在 return，`_handle:2775` 也没有第二个人写 `resp`）。真正要改的是**终端编码器对封禁包的处理**。

### 3.3 为什么这个 bug 只在 `a_proto_int` / `b_proto_str` 下出现

`_cn_envelope` 的调用点全文件只有 **3 处**：

| 调用点 | 协议 | `a_proto_int` 分支的后果 |
|---|---|---|
| `:1961` | `'Error'`（封禁包） | **致命**：封禁包被换成 Account_Auth |
| `:3368` | path A 的 Account_Auth | 无感：本来就要 Account_Auth |
| `:3396` | path B 的 Account_Auth | 无感：本来就要 Account_Auth |

而 `_cn_enc_b64` 只被 `:2816` 一处调用。
其它所有协议（1005/4000/26000/1017/24000/1019/8000/…）走的是 **`_cn_send_envelope`**（`:3002-3017`），它的 docstring 就是 *"Encode exactly the object we were given (no cn_wrap_mode re-building)"*（`:3003`），内部直接 `cn_wire.wrap_response(proto_name, obj, rid)`（`:3006`）—— **尊重入参，不受 `cn_wrap_mode` 影响**。这就是为什么客户端**除了登录握手**其余都还能跑。

结论：`a_proto_int` 是"把一切都伪装成 Account_Auth"的实验模式，它只对 `_cn_envelope` 的两个 Account_Auth 调用点无害，对封禁包必然有害。

### 3.4 为什么 111 项自测全过、线上还是坏的

`selftest_banreply.py` 的 T7 三个出口测的是：

| 用例 | 设的开关 | 走到的分支 | 结果 |
|---|---|---|---|
| T7-1 | 无 `cn_resp_format.txt` | `_json_ok`（`:1962`） | PASS |
| T7-2 | `cn_resp_format=cn_envelope`，无 `cn_wrap_mode.txt` | `_cn_envelope` 的 raw_gzip 分支（`:2825-2830`） | PASS |
| T7-3 | `cn_wrap_mode=cn_enc_b64`（`selftest:533`） | `_cn_enc_b64` 落到 `:3178 inner = dict(inner_obj)` | PASS |

**`a_proto_int` 从未被测过**（`selftest_banreply.py` 里 `a_proto_int` 出现 0 次）。而线上恰恰是 `a_proto_int`。
→ **回归测试缺的正是这一格**，§5 把它补上。

---

## §4 DevId 解析失败的候选原因（按可能性排序）

### 4.0 先摆链路（全部 `account_auth_probe.py`）

```
_FRAG_TLS = threading.local()                                  :82
  写入点（全文件只有这 4 处）
    :3337-3338  path A（exp 以 'decrypt+' 开头才进来，:3321/:3324）
    :4545-4546  rl_request_json
    :4635-4636  rl_route / _rl_relay_once
    :4889-4890  rl2_route
  读取点
    :101-102    _req_dict（**消费式**：读完立刻清空 :103-104）
    :1170       _acct_frag_text（只读，注释 :1161-1164 明确写了）

_req_dict(rec)                                                 :97-124
   :101  if _FRAG_TLS.seq == id(rec): _frag_tls = _FRAG_TLS.v
   :103-104  _FRAG_TLS.v = None ; _FRAG_TLS.seq = None        ← 一次性令牌
   :109  rec['req_devid_src'] = 'fragment' if frag else 'fallback'
   :111  frag = rec.get('req_frag_head')                      ← 已脱敏，永远是空/不可解析
   :123  devid_stash(rec, _d)

devid_stash(rec, d)                                            :642-656
   :649  rec['req_DevId']         = mask_secret(dv, keep=(0,0))   ← 完全脱敏
   :651  rec['req_DeviceUniqueId']= mask_secret(du, keep=(0,0))
mask_secret(v, keep=(0,0))                                     :217-225
   -> "%s****%s(len=%d,sha8=%s)" % (s[:0], '', len, sha8)
   -> 实际是 '****(len=9,sha8=1a2b3c4d)'  ← **非空字符串！**

acct_apply_to_auth(inner, rec)                                 :127-187
   :135  req = _req_dict(rec)
   :136-139  if not req: req = {'DevId': rec.get('req_DevId') or '',        ← 把脱敏垃圾当 DevId
                                'DeviceUniqueId': rec.get('req_DeviceUniqueId') or '',
                                'Token': rec.get('req_Token') or ''}
   :140  ident = svc.identify(req)
   :152-156  _exists = svc.get_account_by_dev_id(_dev) is not None   (异常 -> None)
   :157-165  True->'exact' / (False and trusted)->'create' / else->'retarget-fallback'
   :183-187  外层 except -> acct_svc='fallback:'+类型（**不写 acct_id_src**）

account_service.identify                                      _baseline/account_service.py:501-543
   :517  DevId 非空且不是 ''/'0'/'null'/'None' -> dev_id = 它, source='DevId'
   :521  DeviceUniqueId -> 'duid:<lower>', source='DeviceUniqueId'
   :523-526  两者都没有 -> **raise AuthRejected**
```

关键推论（后面排序就靠它）：

- **`identify()` 在 DevId 与 DeviceUniqueId 都为空时抛 `AuthRejected`**（`account_service.py:523`），异常被 `:183` 兜住并写 `acct_svc`，**`acct_id_src` 根本不会被写**。
  → 所以：**日志里出现 `acct_id_src` ⟹ `req` 里 `DevId`（或 `DeviceUniqueId`）非空 ⟹ 该请求内 `_req_dict` 至少成功过一次**（因为 `req_DevId` 只有 `devid_stash:649` 会写）。
- **`acct_id_src='retarget-fallback'`（`:165`）只在 `_exists is None` 时出现**，而 `_exists` 为 None 只有两种可能：`_dev` 为空，或 `get_account_by_dev_id` **抛异常**（`:154-156` 把异常吞成 None）。
- **`_trusted` 恒为 True**：`identify` 只会把 `dev_id_source` 设成 `'DevId'`/`'DeviceUniqueId'`（`:516/:521`，`Identity` 默认也是 `'DevId'`），所以 `:159` 的 `_exists is False and _trusted` 一旦查库返回"没有"就必然是 `'create'`，**不可能**是 `'retarget-fallback'`。

### 4.1 【最可能，结构性问题】path B 从不填 `_FRAG_TLS`，`_req_dict` 必然返回 `{}`

- **判据**：`_FRAG_TLS` 的写入点只有 `:3337`（path A）、`:4545/:4635/:4889`（relay）。
  path B（`exp` 不以 `decrypt+` 开头）下这几个点**一个都到不了**；`:111` 的 `req_frag_head` 又被 `:3346` 用 `mask_secret` 脱敏过（`'abcd****…(len=…,sha8=…)'`），`json.loads` 必失败 → `:122 return {}`。
  → path B 下 `_req_dict` 返回 `{}`、`req_devid_src='fallback'` 是**确定性结果**，不是偶发。
- **与现场吻合**：20:29:08 时是 path A（`pub_src=devid`、`req_devid_src=正常`、`acct_id_src=exact` 全对得上）；20:36/20:37 变成 `fallback`，说明**这中间 `cn_bridge_exp.txt` 被改了**（大概率是配 round18 的 `cn_wrap_mode=a_proto_int` 时把 exp 清空了，`:3250` 的注释也写着"线上是空 = path B"）。
- **验证**（服务器上，只读）：

```bash
# 1) 当前 exp 是什么（path A 的闸门）
cat -A /www/wwwroot/bapatch/cn_bridge_exp.txt ; echo "---"
#    含 'decrypt+' -> path A；空/别的 -> path B

# 2) 两个开关
cat /www/wwwroot/bapatch/cn_resp_format.txt   # cn_envelope
cat /www/wwwroot/bapatch/cn_wrap_mode.txt     # a_proto_int

# 3) 全量统计 req_devid_src 分布（path B 应该是 100% fallback）
grep -o '"req_devid_src": "[a-z]*"' /www/wwwroot/bapatch/logs/api_all_requests.log \
  | sort | uniq -c

# 4) 看 20:36:07 / 20:37:24 两条原始 rec（这些字段已经都在日志里了）
python3 - <<'PY'
import json
for ln in open('/www/wwwroot/bapatch/logs/api_all_requests.log', encoding='utf-8'):
    try: r = json.loads(ln)
    except Exception: continue
    if r.get('banreply') == 'hit':
        keep = ('t','path','protocol_name','exp','decrypted','fallback','wrap_mode',
                'req_devid_src','req_devid_len','req_devid_sha8','acct_id_src',
                'acct_id_retarget','acct_svc','acct_err','acct_server_id','resp_len',
                'banreply_err','req_frag_len')
        print({k: r.get(k) for k in keep})
PY
```

### 4.2 【次可能，能解释 20:37:24 的 `exact`+`fallback` 矛盾组合】`_req_dict` 一次性消费 + 脱敏 DevId 回流

- **机制**（三行代码组成的连环）：
  1. `_req_dict:103-104` 读完**立刻清空** `_FRAG_TLS`；
  2. 同一请求内若 `_cn_enc_b64` 被走两次（例：`banreply_response:1961` 一次 + 落空后 path B `:3396` 又一次；或 relay 重入），第 2 次 `_req_dict` 必然 `{}` → `req_devid_src='fallback'`；
  3. `:137` 于是退回 `rec['req_DevId']`，而那是 `mask_secret(keep=(0,0))` 的产物 `'****(len=9,sha8=1a2b3c4d)'`（`:649` + `:217-225`）—— **一个非空、可入库、可被 `identify` 当真的假 DevId**。
- **为什么正好解释那两条日志**：
  - 20:36:07 首次把假 DevId 喂进去 → 库里没有 → 若查库抛异常（见 4.3）则 `_exists=None` → `'retarget-fallback'`；若不抛则应是 `'create'`。
  - 20:37:24 假 DevId 已经被建成过一行 → `get_account_by_dev_id('****(len=…,sha8=…)')` **命中** → `'exact'`；而 `req_devid_src` 仍是第 2 次调用写的 `'fallback'`。**`acct_id_src` 与 `req_devid_src` 来自同一次调用，但 `rec` 是同一个 dict，两个字段可能被不同次序的调用分别覆盖** —— 这就是"`exact` 却 `fallback`"的成因。
  - 副作用（比封禁更严重）：**每出现一次这种假 DevId，accounts.db 就多一个 `****…` 的垃圾账号**，且它会被后续请求当成"老玩家"命中。
- **验证**：

```bash
# A) 假 DevId 是否真的进了 accounts.db（铁证，只读）
sqlite3 /www/wwwroot/bapatch/data/accounts.db \
  "SELECT server_id, dev_id, nickname, state, created_at FROM accounts
    WHERE dev_id LIKE '****%' OR dev_id LIKE '%(len=%' ORDER BY server_id DESC LIMIT 20;"

# B) 日志里 req_devid_sha8 是否还在（判据：req_devid_src=fallback 却有 req_devid_sha8）
#    devid_stash:653-654 写的 req_devid_len / req_devid_sha8 是**真 DevId** 的长度与 sha8。
#    它们存在 => 本请求内 _req_dict 成功过一次；同时 req_devid_src=fallback => 之后又被调了一次。
#    这一组合就是 §4.2 "两次调用"的铁证（不需要算任何哈希）。
python3 - <<'PY'
import json
for ln in open('/www/wwwroot/bapatch/logs/api_all_requests.log', encoding='utf-8'):
    try: r = json.loads(ln)
    except Exception: continue
    if r.get('req_devid_src') == 'fallback' and r.get('req_devid_sha8'):
        print(r.get('t'), 'src=', r.get('req_devid_src'),
              'sha8=', r.get('req_devid_sha8'), 'len=', r.get('req_devid_len'),
              'acct_id_src=', r.get('acct_id_src'), 'acct_svc=', r.get('acct_svc'))
PY
```

- **能自证的日志（一行，加在 `acct_apply_to_auth:140` 与 `:173` 之间）**：

```python
acct_log('[devid] req_devid_src=%r req_DevId=%r ident.dev_id=%r src=%r exists=%r -> %r' % (
    rec.get('req_devid_src'), rec.get('req_DevId'), getattr(ident,'dev_id',''),
    getattr(ident,'dev_id_source',''), _exists, rec.get('acct_id_src')))
```
  只要 `ident.dev_id` 里出现 `****(len=` 或 `(len=`，4.2 就成立；只要 `req_devid_src` 在同一行前后变过两次，4.2 的"两次调用"就成立。

### 4.3 【可能，且会伪装成 4.1】查库异常被吞成 `_exists=None` → 无条件退兜底

- **判据**：`:154-156`
  ```python
  except Exception:
      _exists = None        # 未知
  ```
  `sqlite3` 的 `OperationalError: database is locked` / `disk I/O error` 都走这里 → `_exists=None` → `:161-165` **无条件 retarget**，即使 DevId 完全正确。
- **危害**：把"数据库偶发错误"变成"把真实玩家踢到兜底号并新建 Shum 账号"，且 **`_exists=None` 这条路径一行日志都不打**（`:156` 只有 pass）。
- **验证**：

```bash
# 1) 这条路径没有任何日志 -> 先看 provider/连接设置
grep -n "journal_mode\|timeout\|isolation_level" /www/wwwroot/bapatch/tools/account_service.py | head
# 2) 桥进程 stderr / 启动日志里有没有 database is locked
grep -i "database is locked\|disk I/O" /www/wwwroot/bapatch/logs/*.log | tail
# 3) 加一行日志确认（见 4.2 的 acct_log，把 _exists 打出来即可区分）
```

### 4.4 【可能，会串号——比 fallback 更危险】`id(rec)` 复用导致跨请求残留命中

- **机制**：`_FRAG_TLS.seq = id(rec)`（`:3338/:4546/:4636/:4890`）用**内存地址**当请求身份。服务端是 `socketserver.ThreadingTCPServer`（`:5005-5006`），**一个 keep-alive 连接一个线程**，所以 `_FRAG_TLS` 会跨该连接上的多次请求存活；而 `rec` 每请求新建（`:2763`），前一个 `rec` 释放后新 `rec` **很容易被分配到同一地址** → `:101` 的 `seq == id(rec)` **假命中** → 本次请求拿到**上一个请求的 fragment**。
- **后果**：不是 `fallback`，而是**直接串到别人的 DevId/账号**。线上若出现"某玩家登录成另一个号"，优先查这条。
- **验证**：日志里加 `rec['rec_id'] = id(rec)`，对比相邻两条是否相同而 DevId 不同。
- **判据**：`req_devid_src='fragment'` 但 `_FRAG_TLS` 那一轮该请求根本没走 path A / relay ⟹ 假命中。

### 4.5 【已排除/次要】relay 钩子填晚了一步

`:4545/:4635/:4889` 这三个写入点，对 `Account_Auth` 来说都发生在 `:3396`（path B 的 `_cn_envelope`）**之后**（relay2 在 `:3479`，relay A 只在 `name is None` 时进 `:3305`）。所以它们对 auth 的 DevId **没有帮助**，只能在"下一次请求"里被 `id(rec)` 假命中（见 4.4）。**不是本次的主因，但它让 4.4 更可能发生。**

### 4.6 【已排除/次要】`cn_multiacct` 关着导致 banreply 与 auth 身份来源不同

`acct_pub_for` 第一行就 `if not cn_multiacct_on(): return None`（`:1260-1263`），banreply 随后改用 `_acct_pub_by_sid` / `EnterTicket`（`:1876-1883`）。
这**不会**让 banreply 失效（它还有 `handler._cn_decode_any` 直读 packet，`:1940-1944`，20:36/20:37 的 `reason='永久'` 就证明它成功解析到了 pub=854071516），但会让"封禁判定用的身份"和"auth 建号用的身份"**来自两条不同通路** —— 这正是现场"封禁挂在 854071516、auth 却建了 9000000001"的直接观感来源。

---

## §5 修复方案（**未实施**，仅方案）

> 统一前提：线上配置 `cn_resp_format=cn_envelope` + `cn_wrap_mode=a_proto_int` **不改**（那是 round18 的实验开关，改它等于换掉整个实验）；
> 修的是"封禁包不该被这个实验模式重写"。

### 5.A 封禁包被覆盖

#### A-1（最小改动，1 行，**推荐做主修**）

**改动点**：`account_auth_probe.py:1960-1961`

```diff
-        if cn_resp_format() == 'cn_envelope':
-            return handler._cn_envelope('Error', inner, rec)
+        if cn_resp_format() == 'cn_envelope':
+            # [BANREPLY-FIX-A] 封禁包绝不过 cn_wrap_mode 的实验分支：
+            # _cn_send_envelope 的契约就是"原样编码我给的对象"(:3003)，不受 a_proto_int 影响。
+            return handler._cn_send_envelope('Error', inner, rec)
         return handler._json_ok('Error', inner)
```

**为什么是这一行**：
- `_cn_send_envelope:3002-3017` 的 docstring 就是 *"Encode exactly the object we were given (no cn_wrap_mode re-building)"*，内部 `cn_wire.wrap_response(proto_name, obj, rid)`（`:3006`）→ 外层 `protocol` 就是 `'Error'`，与
  - `cn_wire` 自带 selftest（`_bridge_ref/cn_wire.py:140`：`o2['protocol'] == 'Error'`）、
  - 官方 `CreateProtocolErrorResponse`（`GatewayController.cs:781`，见 `:1924-1928` 注释）、
  - `verify_banreply.py:177-187` 的三条断言
  **全部一致**。
- 它绕开了 `:3021` 的整段实验分支，也绕开了 `:3026` 把协议名硬写成 `'Account_Auth'` 的问题。
- 1017/24000/1005/CallName/Nickname/path D 早就在用这个出口（`:2964/:3006/:3417/:3437/:3492`），**是被线上验证过能通的出口**。

**风险**：
1. `_cn_send_envelope:3013-3016` 会覆盖写 `/www/wwwroot/_ba_state/last_direct_envelope_plain.txt`（调试落盘）—— 无害，但会改变该文件的"最后一次"含义。
2. 它**不做** `_cn_envelope:2813-2814` 的 `apply_field_patch` / `apply_flatten`，也不写 `canary` / `hash_echo`（`:2836-2849`）。封禁包本来就不该有那些 AccountAuthResponse 键；若当时正开着 `cn_canary.txt`，封禁包将不带 canary —— 这是**期望行为**（canary 是给 Account_Auth 探针用的）。
3. 封禁包不再落 `round18_A_*.bin/txt` —— 反而修掉了"round18 明文被封禁请求污染"的问题。

#### A-2（"包一旦生成就一定发出去"的结构性保证，~8 行，建议同批上）

> 用户要求的"最外层出口优先判断"。**只上 A-1 也能修好当下**，A-2 是把"以后谁再动编码器也不会再丢"变成结构性事实。

**改动点 1**：`banreply_response:1960-1962` 里把 wire 记到 `rec`（私有键，`_log` 会序列化它，注意别塞二进制）：

```diff
         if cn_resp_format() == 'cn_envelope':
-            return handler._cn_send_envelope('Error', inner, rec)
+            _r = handler._cn_send_envelope('Error', inner, rec)
+            if isinstance(rec, dict):
+                rec['_banreply_wire'] = _r[1]          # bytes，唯一真源
+                rec['_banreply_ctype'] = _r[2]
+            return _r
```

**改动点 2**：`_handle:2775-2779` 之后、`:2780` 之前，加最终出口断言：

```diff
         except Exception as e:
             rec['err'] = repr(e)
             code, resp, ctype = 500, json.dumps({'error': repr(e)}).encode(), 'application/json'
+        # [BANREPLY-FIX-A2] 命中即必发：封禁包是唯一真源，任何后续路径都覆盖不了它
+        _bw = rec.get('_banreply_wire')
+        if _bw:
+            code, resp, ctype = 200, _bw, rec.get('_banreply_ctype') or 'text/plain; charset=utf-8'
+            rec['_send_opts'] = {'ctype': ctype, 'close': True}
+            rec['banreply_served'] = 'forced-at-exit'
         ov = http_override()
```

**注意**：`rec` 会被 `_log:2717-2722` 整个 `json.dumps`，bytes 不能直接进 `json`。所以 A-2 落地时必须把 `_banreply_wire` 在 `_log` 之前 `pop` 掉，或者干脆**不放进 rec**，改用函数返回值穿线（更干净：`_bridge` 已经把元组返回上来了，A-1 之后它本来就正确）。
→ **折中方案**：A-2 只保留断言、不搬运 bytes：

```diff
+        if rec.get('banreply') == 'hit' and not rec.get('banreply_served'):
+            rec['banreply_served'] = 'MISS'    # 命中却没按封禁包发出 -> 一定是又被覆盖了
```
把 `banreply_served='MISS'` 当**监控红线**（`grep -c '"banreply_served": "MISS"'` 必须恒为 0），比强行改写出口更安全，也不会破坏 `_log`。

**A-2 建议采用"断言版"**：加 `rec['banreply_served']`（A-1 成功路径上置 `'direct_envelope'`），出口处若 `banreply=='hit'` 而 `banreply_served != 'direct_envelope'` 就置 `'MISS'` 并 `acct_log` 告警。零行为风险，纯可观测性 + 红线。

#### A 的验证（不依赖客户端）

**V1 — 用现成的 `verify_banreply.py`（最强，直接打 9097）**

```bash
# 造一条永久封禁（用被封号的 pub）
PUB=854071516
sqlite3 /www/wwwroot/bapatch/data/accounts.db \
  "INSERT OR REPLACE INTO bans(kind,target,until_epoch,reason,created_at,created_by)
   VALUES('account','$PUB',NULL,'联调','2026-11-18 20:00:00','ops');"
printf '1' > /www/wwwroot/bapatch/cn_banreply.txt

# 打桥（脚本自己按客户端格式加密，断言 outer.protocol=='Error' / ErrorCode==1025 / BanReason）
python3 verify_banreply.py --pub $PUB --devid $PUB --port 9097 --until 永久 --show
```
- **修前**：`[FAIL] outer.protocol != "Error"（拿到 'Account_Auth'）` + `[FAIL] inner.ErrorCode != 1025`，`HTTP 200  3500 B`。→ 这就是本 bug 的复现器。
- **修后**：`HTTP 200  ~300 B`，三条全 `[PASS]`。
- ⚠️ 它需要桥的 `tools/` 目录（`cn_cipher/cn_wire/aes_pure`），见 `MD5.txt` 说明。

**V2 — curl 直打 9097**（`VERIFY.md` §1.3 现成配方，`:100-111`）：

```bash
TOKEN=AHTQLQI65FWJGGGK4KL5AEF57A          # Account_Auth(1002)
PKT=$(python3 - <<'PY'
import sys; sys.path.insert(0,'/www/wwwroot/bapatch/tools')
import cn_cipher
frag = ',"DevId":"854071516","ClientUpTime":1,"Hash":4294967303}'
frag = frag[:-1] + ' ' * (373 - len(frag)) + '}'
print(cn_cipher.wrap_packet(cn_cipher.build_inner(frag)))
PY
)
printf -- '--X\r\nContent-Disposition: form-data; name="protocol"\r\n\r\n%s\r\n--X\r\nContent-Disposition: form-data; name="encode"\r\n\r\ngzip\r\n--X\r\nContent-Disposition: form-data; name="packet"\r\n\r\n%s\r\n--X--\r\n' "$TOKEN" "$PKT" \
 | curl -sS -i -X POST http://127.0.0.1:9097/api/account/auth \
        -H 'Content-Type: multipart/form-data; boundary=X' \
        -H 'User-Agent: BestHTTP/2 v2.4.0' --data-binary @-
```
判读：`Content-Length` 从 ~3500 掉到 ~300；把响应体 base64 解回来（`cn_wire.unwrap_response`）应见 `protocol:"Error"`、`ErrorCode:1025`、`BanReason:"永久"`。

**V3 — 两个落盘文件（最省事的旁证）**

```bash
# 修后：封禁请求的明文应该出现在 last_direct_envelope_plain.txt（_cn_send_envelope:3014）
grep -o '"ErrorCode":1025' /www/wwwroot/_ba_state/last_direct_envelope_plain.txt
grep -o '"BanReason":"[^"]*"' /www/wwwroot/_ba_state/last_direct_envelope_plain.txt
# 修后：round18_A_plain.txt 不再被封禁请求写（mtime 应停在被封号登录之前）
stat -c '%y' /www/wwwroot/_ba_state/round18_A_plain.txt
```

**V4 — 日志红线（每次部署后都要看）**

```bash
grep -c '"banreply_served": "MISS"' /www/wwwroot/bapatch/logs/api_all_requests.log   # 必须 0
```

**回滚**：A-1 是单行，`cp account_auth_probe.py{.bak,}` + 重启桥；或直接还原 md5 `215feddd3ecf281cd61273149b89fd91` 那一份（`VERIFY.md` §0 `:24-28` 的 `cp ... .$(date +%Y%m%d-%H%M%S).bak` 流程）。**开关级回滚**（不重启、不换文件）：`rm /www/wwwroot/bapatch/cn_banreply.txt` → 封禁拦截整体关闭，桥回到"只登录不拦"的状态，其他功能不受影响。

---

### 5.B DevId 解析失败

分三层，**建议 B-1 + B-2 同批**；B-3 是止血（防垃圾号），可单独上。

#### B-1（治本，~6 行）path B 也把明文片段放进 `_FRAG_TLS`

**改动点**：`_bridge:3244` 之后、`:3245` 封禁 hook 之前插入

```diff
         name = name_fix_resolve(proto_str, rec)   # BAPATCH-NAME-FIX v1
+        # [DEVID-FIX-B1] path B（无 decrypt+）下 _FRAG_TLS 永远空 -> 下游 _req_dict 全 fallback。
+        # 这里解一次明文放进去，身份/多账号/封禁三条路都吃同一份事实。
+        try:
+            if not getattr(_FRAG_TLS, 'v', None) and packet_b64:
+                _f1 = self._cn_decode_any(packet_b64, proto_str)
+                if _f1:
+                    _FRAG_TLS.v = _f1
+                    _FRAG_TLS.seq = id(rec)
+                    rec['frag_src'] = 'bridge-predecode'
+        except Exception as _f1e:
+            rec['frag_pre_err'] = repr(_f1e)
         # >>> BAPATCH-BANREPLY v1 Hook BEGIN >>>
```

**为什么有效**：`_req_dict:101-102` 就能从 `_FRAG_TLS` 拿到真 fragment → `devid_stash` → `identify` 拿到真 DevId → `acct_id_src` 走 `exact`/`create`，不再 `retarget-fallback`。
**风险**：每请求多一次 AES 解密（`_cn_decode_any` 内部全 try/except，`:2853-2876`，失败返回 `''`，不会 500）；对非 Account_Auth 协议也会填 `_FRAG_TLS`，可能让 `_acct_frag_text:1170` 拿到"非登录片段" —— 但它本来就会自己解 packet（`:1942`），等价。
**验证**：`grep -o '"frag_src": "[a-z-]*"' api_all_requests.log | sort | uniq -c` 应出现 `bridge-predecode`；`req_devid_src` 分布应从 100% fallback 变成 100% fragment。

#### B-2（治本，2 处小改）去掉"一次性令牌"和"脱敏回流"

**改动点 1**：`_req_dict:103-104` 不再清空（改由请求入口统一清）

```diff
-        _FRAG_TLS.v = None
-        _FRAG_TLS.seq = None
+        # [DEVID-FIX-B2] 不再在这里消费：同请求内可能有多个消费者（acct_apply_to_auth /
+        # _acct_frag_text）。清理统一放到 _handle 的请求入口。
```

**改动点 2**：`_handle:2763`（`rec` 建好之后、`_bridge` 之前）加每请求复位

```diff
                'body_printable': ''.join(...)}
+        try:
+            _FRAG_TLS.v = None
+            _FRAG_TLS.seq = None
+        except Exception:
+            pass
         t0 = time.time()
```

**改动点 3**：`:136-139` 不再把脱敏值当身份

```diff
         if not req:
-            req = {'DevId': rec.get('req_DevId') or '',
-                   'DeviceUniqueId': rec.get('req_DeviceUniqueId') or '',
+            def _clean(v):
+                v = v or ''
+                return '' if ('****' in v or '(len=' in v) else v      # 脱敏值绝不当身份
+            req = {'DevId': _clean(rec.get('req_DevId')),
+                   'DeviceUniqueId': _clean(rec.get('req_DeviceUniqueId')),
                    'Token': rec.get('req_Token') or ''}
```

**为什么必须改 3**：`devid_stash:649` 存的是 `'****(len=9,sha8=…)'`（`mask_secret keep=(0,0)`，`:217-225`），它**非空**，会被 `identify:517` 当合法 DevId，进而 `get_or_create_account` **真的建出一个以 `****…` 为 dev_id 的账号**。§4.2 的假 `exact` 就是这么来的。
**风险**：改 1/2 后 `_FRAG_TLS` 生命周期变长 → 必须配 2 的每请求复位，否则 4.4 的串号风险放大。三处必须一起上。
**验证**：

```bash
# 假 DevId 不再新增（跑一段时间后）
sqlite3 /www/wwwroot/bapatch/data/accounts.db \
  "SELECT COUNT(*) FROM accounts WHERE dev_id LIKE '****%' OR dev_id LIKE '%(len=%';"
# 断言：不增长。存量垃圾号请人工确认后清理（本轮不动库）
```

#### B-3（可选，止血）给 `_exists=None` 留痕 + 不静默 retarget

**改动点**：`:154-156`

```diff
                 try:
                     _exists = svc.get_account_by_dev_id(_dev) is not None
-                except Exception:
-                    _exists = None                      # 未知
+                except Exception as _qerr:
+                    _exists = None                      # 未知
+                    rec['acct_devid_query_err'] = repr(_qerr)
+                    acct_log('[acct] get_account_by_dev_id(%r) 查询失败，将退兜底: %r' % (_dev, _qerr))
```
**风险**：零（只加日志）。**价值**：把 §4.3 那条"数据库偶发错误 → 玩家被踢到兜底号"变成可见的。
**验证**：`grep -c acct_devid_query_err api_all_requests.log` 应为 0；不为 0 就说明 4.3 是主因之一。

#### B 的验证（不依赖客户端）

| 目的 | 命令 |
|---|---|
| 确认线上是 path B | `cat -A /www/wwwroot/bapatch/cn_bridge_exp.txt`（空 = path B） |
| 修前基线 | `grep -o '"req_devid_src": "[a-z]*"' logs/api_all_requests.log \| sort \| uniq -c` → 全 `fallback` |
| 修后 | 同上 → 全 `fragment`；且 `acct_id_src` 出现 `exact`（真号）而不再是 `retarget-fallback` |
| 端到端 | `python3 verify_banreply.py --pub 854071516 --devid 854071516` → banreply 命中且 `acct_pub=854071516` |
| 回归（关键） | 把 §3.4 缺的那格补进 `selftest_banreply.py`：`cn_resp_format=cn_envelope` **且** `cn_wrap_mode=a_proto_int`，断言 `outer.protocol == 'Error'` 且 `ErrorCode == 1025`。**修前必 FAIL，修后必 PASS** —— 这一格就是本次事故的回归测试。 |

**回滚**：B 的改动若出问题，先回 B-3（纯日志）→ 再回 B-2 的改动 1/2（恢复消费语义）→ B-1 可单独 `git` 级回退。三者都在 `_bridge` 入口/`_req_dict`/`_handle` 的小块，互不依赖，可逐块回滚。**开关级回滚**：无（B 没有开关），所以建议 B-1 先加一个 `CN_DEVID_FRAG=0` 环境变量门，便于不换文件关掉。

---

## §6 不确定项

### 6.1 「20:37:24 的 `acct_id_src=exact` 到底是"真号"还是"垃圾号被命中"」

- 两种都能解释 `req_devid_src=fallback` + `acct_id_src=exact` 同时出现（§4.2 给了机制）；
- **`acct_server_id=10000000005` 这一项不具判别力**：`acct_apply_to_auth:181` 写的是**本次**那行的 `ServerId`，两次请求都写它。
- **判别命令**（一条就够）：

```bash
sqlite3 /www/wwwroot/bapatch/data/accounts.db \
  "SELECT server_id, dev_id, nickname, state, publisher_account_id
     FROM accounts WHERE server_id = 10000000005;"
```
`dev_id` 是 `9000000001`（兜底）还是 `****(len=…`（垃圾）还是真实 DevId —— 一眼定死。
- 若为 `9000000001`：20:37:24 是 `retarget-fallback` 之后**又命中兜底号**（`identify` 拿兜底号回查），说明两次 `acct_apply_to_auth` 的次序与我推的相反；
- 若为 `****(…`：§4.2 完全成立，**垃圾号已经进了库**，B-2 的改动 3 必须上。

### 6.2 「封禁包返回值是否真的被 `_bridge:3256` return 了」（§1.2-B 的 i / ii）

不影响修法（A-1 两种情况都修），但影响"要不要顺带修 `banreply_response` 的异常兜底"。
**判别命令**：看 20:36/20:37 那两条 rec 里有没有 `banreply_err` 或 `fallback`：

```bash
python3 - <<'PY'
import json
for ln in open('/www/wwwroot/bapatch/logs/api_all_requests.log', encoding='utf-8'):
    r = json.loads(ln) if ln.strip().startswith('{') else {}
    if r.get('banreply') == 'hit':
        print(r.get('t'), 'banreply_err=', r.get('banreply_err'),
              'fallback=', r.get('fallback'), 'wrap_mode=', r.get('wrap_mode'))
PY
```
- `banreply_err` 有值 → 情形 (ii)（编码抛异常被吞），还要修 `:1963-1970`；
- 两者都空 + `wrap_mode='a_proto_int'` → 情形 (i)（正常 return，内容被换），**只需 A-1**。

### 6.3 「resp_len=3500 的 33 键 vs 本机 32 键」

本机 `cn_inner27.build(1002)` 出 **32 键**，线上落盘 **33 键**。差的 1 个键本机无法确定（`_baseline/cn_inner27.py` 与线上 `tools/cn_inner27.py` 未必同版；`:2899` 的注释就写着"线上 bridge 与本仓库副本不是同一版"）。
最可能是线上 `cn_inner27.py` 多一个字段，或 `acct_apply_to_auth` 后的 `apply_flatten`（`:990-1014`）在线上对重建后的 inner 也跑了一次。
**不影响结论**：`Protocol=1002`(int) + 无 `ErrorCode/BanReason` 已足以锁定 `:3023`。

### 6.4 「`get_account_by_dev_id` 在那个时刻是否抛过异常」（§4.3）

纯运行时事实，静态推不出来。靠 B-3 的日志或 `database is locked` 的进程 stderr 判定。

### 6.5 「`_FRAG_TLS` 的 `id(rec)` 假命中在本机无法复现」

需要 CPython 分配器的具体行为 + 同一 keep-alive 连接的多请求序列。**只能在线上用 `rec['rec_id']=id(rec)` 的日志判定**（§4.4 的判据）。这条即使不成立也不影响 §4.1/§4.2。

---

## 附录 A：产物位置

| 文件 | 用途 |
|---|---|
| `work/ba/plan/20261118/BANREPLY_OVERRIDE_STUDY.md` | **本文**（定位 + 方案），路径按 §产出 指定 |
| `work/ba/plan/20261118/_banreply_bug/_len_probe.py` | **只读**长度探针：不 import 桥、不加密，用纯长度算术对比"封禁包 ≈300 B / a_proto_int 重建 ≈2136 B"，反解 `resp_len=3500` 需要的明文长度。跑法 `python _len_probe.py` |
| `work/ba/plan/20261118/_banreply_bug/_len_probe_out.txt` | 探针输出 |

> `_len_probe.py` 只读 `_baseline/cn_inner27.py`，不写任何文件、不碰线上、**不是补丁**。
> 本轮未修改任何既有文件：`_build_banreply/` 下 8 个文件的 mtime 与内容均未动（基线 md5 未变）。

## 附录 B：一句话总结

- **A（封禁包）**：`_build_banreply/account_auth_probe.py:3023`，`_cn_enc_b64` 的 `a_proto_int` 分支（`:3021` 闸门）无条件 `inner = cn_inner27.build(1002)`，把 `banreply_build:1911-1914` 造好的 4 键封禁内层丢掉并重建成 Account_Auth；`:3256` 的 `return` 是好的，所以修法是**把封禁包的终端编码换成 `_cn_send_envelope`（`:1961` 一行）**，不是加 return。
- **B（DevId）**：path B 不填 `_FRAG_TLS`（写入点只在 `:3337/:4545/:4635/:4889`），`_req_dict` 必然 `{}`（`:109` → `fallback`）；再叠加 `:103-104` 的一次性清空与 `devid_stash:649` 的脱敏值回流（`:137`），把 `'****(len=…)'` 当成 DevId 喂给 `identify`（`account_service.py:517`）。
- **回归测试缺口**：`selftest_banreply.py` 的 T7 只测 `cn_wrap_mode=cn_enc_b64`（`:533`），**从未测 `a_proto_int`** —— 补这一格，本 bug 就会在 CI 里当场 FAIL。
