# 下一轮补丁规格：identify 真身份 + 堵明文落盘

> 状态：**规格定稿，未实现、未部署**
> 前置：`account_auth_probe.py` 的线上基线必须先拉到 `srv_live\<TS>\` 并校验 md5（见 §0）
> 原则：一次重启做完；明文只在内存流动；任一验收不过立即回滚

---

## 0. 基线纪律（上一轮的教训）
```
① 线上 acct 探测桥 = /www/wwwroot/bapatch/tools/account_auth_probe.py
② 动手前必须: md5sum + wc -c + 拉到 srv_live\<TS>\bapatch\tools\ 并校验一致
③ 补丁必须基于该副本；交付物写明「基线 md5 → 补丁后 md5 → diff 行数」
④ 写不出的 md5 一律当不存在
```

---

## 1. 已闭合的事实（有样本支撑，不是推断）

```
F1  客户端确实发 DevId / DeviceUniqueId / Token
    → req_frag_head 键名扫描 190 个样本命中三者

F2  完整明文一直在 r['fragment'] 里
    → cn_cipher.decode_packet() 返回 {'fragment': 完整明文, 'frag_len': N}
    → :2285 才做 [:600] + mask_secret，**只为写日志**
    → :83-88 _req_dict(rec) 读的却是 rec['req_frag_head']（日志副本）
    ⇒ identify 的输入源自伤：截断 + 打码 ⇒ JSON 解析必失败 ⇒ 走兜底

F3  rec 就是落盘对象
    → :1724 建 rec · :1757 self._log(rec) · :1678 json.dumps(rec) → api_all_requests.log
    ⇒ **任何塞进 rec 的键都会进日志**（我原先的 rec['req_frag_full'] 方案因此作废）

F4  _req_dict(rec) 有副作用 :96 devid_stash(rec, _d)
    → :589 rec['req_DevId']=原值 · :591 rec['req_DeviceUniqueId']=原值

F5  另外两处独立明文写入
    → :2288 rec['req_Token']     = req_json.get('Token')   原值
    → :1420 rec['acct_mxtoken']  = sk.get('MxToken')       原值

F6  落盘条数（/www/wwwroot/bapatch/logs/api_all_requests.log，8.6 MB）
      req_DevId             52      明文
      req_DeviceUniqueId     52      明文
      req_Token            223      明文
      acct_mxtoken         120      明文（MxToken = 会话凭证）
      req_key / req_iv    1969      待复核是否真明文

F7  web 可达性：`tools/` 与 `logs/` **不在任何 nginx root/alias 树内**
    → 只有 /www/wwwroot/bapatch/noroot_payloads 被映射
    ⇒ api_all_requests.log 定级「隐患」不「事故」
    ⇒ /www/wwwroot/_ba_state/*_plain.txt（完整响应明文含 SessionKey）**定级待定**，正在查

F8  devid_on() 依赖 /www/wwwroot/bapatch/cn_devid.txt 内容 ∈ {1,on,true,yes}，当前 = `1`
    ⇒ 调试开关在生产机上处于**开启**状态
```

---

## 2. 改动清单

### P1 · 旁路通道（明文不进 rec）
```
文件顶部（已有 import threading、_RL_LOCAL 等）新增：
    _FRAG_TLS = threading.local()

★ 注入点必须**无条件**，在 `if isinstance(req_json, dict)` 外面（行号用 grep 核准）：
```
2271:  r = cn_cipher.decode_packet(packet_b64, proto_str)
2275:  if r is not None:
2276:      rec['decrypted'] = True
2277:      rec['req_key']      = mask_secret(r.get('key'))
2279:      rec['req_inner_len'] = r.get('inner_len')
2280:      rec['req_frag_len']  = r.get('frag_len')
        ← ★★ 在这里插入 ★★
           try: _FRAG_TLS.v   = r.get('fragment') or None
                _FRAG_TLS.seq = rec.get('t') or rec.get('Hash')
           except Exception: _FRAG_TLS.v = None
2281:      req_json = r.get('json')
2282:      if isinstance(req_json, dict):      ← 这一路 req_json 恒为 None，进去就错了
2285:          rec['req_frag_head'] = mask_secret(str(r.get('fragment'))[:600])
```
**为什么必须在这里**：线上这一路 `req_json` 是 `None`（协议 token 不在 decode_packet 映射表里）
⇒ `req_frag_head` / `req_Token` 在这条路径上**从来没被写过**
⇒ `_req_dict(rec)` 返回 `{}` ⇒ `acct_apply_to_auth` 用空的 `rec['req_DevId']` ⇒ identify 兜底。

其余三处 relay 写入点同样要灌 TLS（它们都拿到了完整 `_frag`）：
```
3469:  rec['req_frag_head'] = mask_secret(text[:300])
3554:  rec['req_frag_head'] = mask_secret(_frag[:300])
3802:  rec['req_frag_head'] = mask_secret(_frag[:300])
```
以及 `_cn_decode_any`（1814-1820）—— 它已经拿到完整 `frag` 并 return，是最干净的注入点。

**原则：只要解密出完整 fragment 就灌 TLS；写进 `rec` 的永远是截断+脱敏版。**
**禁令：不许把明文写进 `rec`、不许 `print`、不许进任何 `_log()`。**

### P1b · 线程配对（硬要求）
```
3911: socketserver.ThreadingTCPServer.allow_reuse_address = True
3912: with socketserver.ThreadingTCPServer(('127.0.0.1', 9097), Handler) as s:
```
⇒ 每连接一线程；同一连接可能处理多个请求（keep-alive）⇒ 只"用完置 None"不够稳。
赋值时同时记 `_FRAG_TLS.seq`，消费端比对一致才用；不一致当没有。**串号比拿不到更危险。**

### P1c · 调用点的事实（不要重构这段）
```
100:  def acct_apply_to_auth(inner, rec)
1981:     if cn_wrap_mode() in ('a_proto_int', 'b_proto_str'):   ← 唯一调用点在这个分支内
1984:         inner = acct_apply_to_auth(inner, rec)
其余分支（2007/2029/2046/2065/2084/2135）用 cn_inner.build(...)，不碰真实 AccountDB
```
线上这个分支**是活的**：`rec['acct_mxtoken']` 只有 `acct_apply_to_auth`（:123）会写，日志里有 **120 条**。
⇒ **不要动 1981-1984 的结构**，只换 `_req_dict` 的输入源。

### P2 · 消费端切换输入源
```
:82-97 _req_dict(rec) 改成：
    frag = ''
    try:
        _sq = getattr(_FRAG_TLS, 'seq', None)
        if _sq and _sq == (rec.get('t') or rec.get('Hash')):
            frag = _FRAG_TLS.v or ''
    except Exception:
        frag = ''
    if not frag:
        frag = (rec.get('req_frag_head') or '').strip()      # 历史兼容
    try:
        _FRAG_TLS.v = None; _FRAG_TLS.seq = None             # 用完即弃
    except Exception:
        pass
    其余逻辑不动（lstrip(',') / 补花括号 / json.loads / devid_stash）
```
**注意**：`devid_stash(rec, _d)` 这行保留（P3 已把它改成只写脱敏值）。

### P3 · 堵漏（四处，只留脱敏形态；行号以 grep 为准）
```
:589  rec['req_DevId']         = mask_secret(dv.strip())
:591  rec['req_DeviceUniqueId']= mask_secret(du.strip())
:2288 rec['req_Token']         = mask_secret(req_json.get('Token'))
:123  rec['acct_mxtoken']      = mask_secret(sk.get('MxToken'))      ← 不是 :1420
新增诊断字段（脱敏，但可用来验证 identify 生效）：
    rec['req_devid_src']  = 'fragment' | 'fallback'
    rec['req_devid_len']  = len(dev_id) if dev_id else 0
    rec['req_devid_sha8'] = hashlib.sha256(dev_id.encode()).hexdigest()[:8] if dev_id else None
```
**`sha8` 是验收的关键**：不泄露原值，但能证明"每次拿到的是同一个真 DevId"。

### P4 · 账号解析安全化（**不做这条，修好 identify 就等于让用户丢档**）
当前：`get_or_create_account` 只按 dev_id 查（:882）⇒ 真 DevId 无对应行 ⇒ **建一个新空号**
```
改成三级：
    row = get_account_by_dev_id(dev_id)        # 有 → 用它
    if not row:
        row = get_account_by_dev_id(str(fallback_pub))   # 无 → 退到 314816420 的老号
    if not row:
        row = create_account(dev_id)           # 都没有 → 才建（真正的全新安装）
```
额外：把观测到的 `dev_id → server_id` 记进 `accounts.shittim_server_id` 之外的一张旁表或日志字段
（脱敏成 sha8），供后续"公益卡绑定设备"使用。**本轮只落诊断，不做绑定。**

### P5 · 关掉调试开关
```
devid_on() 读 /www/wwwroot/bapatch/cn_devid.txt（当前内容 `1` = 开）
改成**代码层面**不再依赖它写原值（P3 已改为只写脱敏值），不要依赖运维去改文件
```

### P7 · 停掉 `_ba_state` 的明文转储（新增，与 P3 同源）
现状：**无条件写**，每次请求覆盖一遍完整响应明文（含 AccountDB / SessionKey）
```
1566:  open('/www/wwwroot/_ba_state/last_direct_envelope_plain.txt','w').write(plain)   ← 无开关
1974:  open('/www/wwwroot/_ba_state/last_direct_envelope_plain.txt','w').write(plain)
1998:  open('/www/wwwroot/_ba_state/round18_%s_wire.bin','wb').write(wire)
1999:  open('/www/wwwroot/_ba_state/round18_%s_plain.txt','w').write(plain)
2022/2023, 2039/2040, 2058/2059, 2077/2078, 2096/2097, 2113/2114, 2125, 2155/2156  同型（共 21 处）
```
改法：
```
模块级加一个默认关闭的开关：
    _PLAIN_DUMP_ON = os.path.exists('/www/wwwroot/bapatch/plain_dump_on.txt')
每个写点包一层：
    if _PLAIN_DUMP_ON:
        try: open(...)...
        except Exception: pass
```
**注意**：`2103` / `2120` 有**读取** `_ba_state/cn_real_capture/resp_1.body` 的地方，
那些在 `real_captured` 实验模式下才会走到（当前模式 `a_proto_int`）。
⇒ **只停写、不删文件**；已有文件处置属 P6。

### P8 · 语义澄清：`mask_secret` 到底长什么样（防止误判）
```python
158: def mask_secret(v, keep=(4, 4)):
162:     if len(s) <= keep[0] + keep[1]: return "*" * len(s)
164:     return "%s****%s(len=%d,sha8=%s)" % (s[:4], s[-4:], len(s), sha256(s)[:8])
```
⇒ 打码形态 = `abcd****wxyz(len=32,sha8=1a2b3c4d)`，**长度 34–40，一定含 `****(`**。
⇒ **判据必须是"含 `****(`"，不能是"是否全星号 / 长度是否 32"**（后者会把打码值误判成明文）。
⇒ 反过来：`mask_secret` 自带的 `sha8` + `len` **正好就是验收要的诊断字段**，不必另造。

⇒ 对 **DevId（9 位，形如手机号）** 要更严：`keep=(4,4)` 会留下 8/9 位，等于没打码。
P3 里 `req_DevId` / `req_DeviceUniqueId` 应改用 `mask_secret(dv, keep=(2, 0))` 或专用脱敏函数。

### P6 · 历史明文处置（**单独批，不在本轮**）
```
目标 1: /www/wwwroot/bapatch/logs/api_all_requests.log   447 条敏感记录
目标 2: /www/wwwroot/_ba_state/*_plain.txt               完整响应明文（含 SessionKey）
方式  : 脱敏重写 / 轮转 + 收紧权限 0600 / 删除（取决于是否还需要取证）
—— 属写操作，必须用户明确批准后才动
```

---

## 3. 验收（**必须同时满足正反两面**）

### 正向
```
A1  accept_accountdb.py 仍然 ACCEPT PASS（12 项）
A2  新的一次登录后，日志里出现 req_devid_src='fragment'（不是 'fallback'）
A3  req_devid_len > 0 且 req_devid_sha8 在多次登录间**稳定不变**
A4  登录后仍然命中 server_id=10000000000（老号），**不是**新建空号
    ← 这是 P4 是否生效的唯一判据；不满足就回滚
```

### 反向（**这一半比正向重要**）
```
B1  新写入的日志记录里，以下键**明文条数必须为 0**：
      req_DevId / req_DeviceUniqueId / req_Token / acct_mxtoken
    判据：这几条记录里对应值必须形如 `****` / `De****`，不含原始长度
B2  `grep -c '"req_devid_sha8"' ` 有值，且**同一条记录里没有完整 DevId**
B3  全文搜不到 fragment 的完整明文（比对 fragment 前 40 字符在新日志中的出现次数 = 0）
```

### 回滚
```
· 补丁前备份 account_auth_probe.py 到 /root/IDENTITY_FIX_BACKUP_<TS>/
· 一条命令：RESTART_CMD='setsid nohup python3 account_auth_probe.py >>/www/wwwroot/bapatch/tools/bridge.restart.log 2>&1 &'
            LAUNCH_DIR='/www/wwwroot/bapatch/tools'
            bash /root/IDENTITY_FIX_BACKUP_<TS>/ROLLBACK.sh
· 回滚后必须复验：9097 单实例 + accept PASS + 账号仍是 314816420
```

---

## 4. 执行顺序（不可打乱）
```
1  srv-ops 拉线上基线 → 报 md5/size          （已下发）
2  proto-analyst 基于该副本出补丁 + 自测       （不许部署）
3  shittim-analyst 独立审计（审计员 ≠ 实现者）
4  srv-ops 部署 → 正向 A1–A4 + 反向 B1–B3 全过才算成功
5  用户登录实测：等级页 / 昵称界面
6  P6 历史明文处置：单独批
```

---

## 5. 这一轮**不做**的事（防止再次摊大）
```
× UnReadMailCount 从列表接口补（独立增量，不捆绑）
× 公益卡/付费卡的规则实现（依赖 P4 的绑定能力，下一轮）
× 8081 TLS
× C# DLL 79fc88e5 上线
× req_key/req_iv 的结论（待复核后再定）
```
