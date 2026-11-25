# WHY_TLS_EMPTY — 最终更正版

> **结论先说**：v3（`7d4d162516c2ac1dd6b140bb6a01779b`）的身份链路是**通的**，h5 执行了。
> 我上一版"接错位置 / 2331 从未执行"的结论**错误**，已撤回。v4（`4d50e6c7…`）作废。

---

## 0. 每一个行号都标注"哪个文件、哪个 md5、多少行"

本次分析涉及三份内容，**必须分开引用**：

| 代号 | 文件 | md5 | 行数（python `split("\n")`） |
|---|---|---|---|
| **BASE** | `bapatch\tools\account_auth_probe.py`（线上基线） | `1db27e4c…` | 3,690 |
| **V3** | `_patched\account_auth_probe.py`（= 线上部署版） | `7d4d1625…` | **3,999** |
| **V4** | 同名文件（中途生成，**已作废**） | `4d50e6c7…` | 4,008 |

> 注：PowerShell `(Get-Content).Count` 在这批文件上会少算（V3 得 3,772），
> 因为它按物理行拆分；**以 python `split("\n")` 的 3,999 为准**。这也是之前行号对不上的一个来源。

**教训（写进纪律）**：报告里任何行号必须写成 `文件 + md5 + 行数 → 行号`；
版本号（BASE/V3/V4）不同的文件**不可混引**。

---

## 1. 用实测字段反推控制流（V3，`/api/account/auth` @ 02:42:43）

| 实测字段 | 只在 V3 的这一行写 | 判据 |
|---|---|---|
| `decrypted: True` | **2336** `rec['decrypted'] = True`（`if r is not None:` 内） | 解码成功 |
| `req_frag_len: 372` | **2340** `rec['req_frag_len'] = r.get('frag_len')` | 同一块 |
| `req_frag_head` len=**372** | **2351** `mask_secret(str(r.get('fragment'))[:600])` | 全文唯一 `[:600]`；relay 三处 `[:300]`、nick `[:300]`、call `[:200]` ⇒ **只能来自这里** |
| `req_keys: [...]` | **2349** `rec['req_keys'] = sorted(req_json.keys())`（`if isinstance(req_json, dict):` 内） | `req_json = r.get('json')`（**2347**）执行且为 dict |
| `req_devid_src: 'fragment'` | `_req_dict` 读到 `_FRAG_TLS.v` | **2342** 注入 + 消费端命中 |
| `req_devid_len: 9` / `sha8: a424da70` | `devid_stash` 末尾诊断 | stash 跑过 |
| `acct_id_src: 'exact'` | P4 块 | `get_account_by_dev_id(真 DevId)` 命中 |

**⇒ 2329 门控为真、2331 解码成功、2335 成立、2348 成立、2342 注入被消费。path A 生效，path B 未到达。**

---

## 2. 我错在哪（准确的错误描述）

1. 我把更早一次观测到的"`req_devid_*` 没有写进日志"当成本次请求的事实；
2. 由"字段缺失"反推"TLS 为空 → h5 没执行 → 走了 path B → 接错位置"；
3. 但 `req_keys` 与 `req_frag_head(len=372)` **在任何 relay / path-B 路径上都写不出来**，它们直接证明 2348/2351 执行过。

**错误类型：用"缺失的字段"反向推断控制流。** 正确做法是用"**存在的字段**"正向锁定位点（见上表）。
另加一条纪律：**引用行号必须带文件 md5**——本轮期间磁盘上同时存在 V3 与 V4 两个版本，混引会造成"同一行号指向不同代码"。

---

## 3. 关于"path B 里本来就有 v4 修正"的核对结果（附证据）

V3（`7d4d1625…`，3,999 行）**没有**那段代码。实测：

```
grep "_rf = cn_cipher.decode_packet"  V3  → 命中 0
V3 :2386-2401 原文：
2386:         if name in ('Account_Auth', 'Account_Auth2'):
2387:             sk, aid = ensure_session(rec)
2388:             if sk is None:
2389:                 return 500, json.dumps({'error': 'checknexon failed'}).encode(), 'application/json'
2390:             req = {"Protocol": "Account_Auth", "SessionKey": sk}
2391:             rec['synth_auth'] = req
2392:             code, raw = post_gateway(req)
2393:             rec['auth_code'] = code
...
```
那段 `_rf = cn_cipher.decode_packet(...) if packet_b64 else None` 属于 **V4**（`4d50e6c7…`）——我在生成 V4 时把它插在 2387，检查 V3 时磁盘上的文件恰好已被重生成回 V3，所以现在 `count=0`。
**结论：V3 不含该块；V4 含；V4 已作废，磁盘上的 `_patched` 现为 V3。**

---

## 4. 处置

- **v4（`4d50e6c7…`）作废**，不部署、不复审；
- **v3（`7d4d1625…`）保留**，实测有效，不回滚；
- 磁盘上 `_patched\account_auth_probe.py` 已重新生成为 **V3 内容**（md5 `7d4d1625…` / 164,514 B / 3,999 行 / diff 8,370 B / 10 hunk），自测 **23/23 PASS**（含断言"FIX5 已不在补丁里"、"h5 注入仍在"）；
- 本议题到此为止，不再投入。
