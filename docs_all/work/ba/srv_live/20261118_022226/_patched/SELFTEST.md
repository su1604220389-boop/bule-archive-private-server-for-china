# SELFTEST — v4（含审计 4 项修正）

> **未部署、未重启桥、未改线上任何文件**
> 基线：`bapatch\tools\account_auth_probe.py`（161,194 B / `1db27e4c5d9074bf8ad15b216327aef4`）
> 补丁：`_patched\account_auth_probe.py` | diff：`_patched\account_auth_probe.diff`

| 项 | 值 |
|---|---|
| 基线 md5 | `1db27e4c5d9074bf8ad15b216327aef4`（校验通过） |
| 补丁后 md5 | `7d4d162516c2ac1dd6b140bb6a01779b` |
| 补丁后体积 | **164,514 B**，净增 **+3,320 B** |
| diff | 8,370 B（UTF-8），**10 个 hunk** |
| 函数数 | 149 → 150（仅新增 `_fallback_dev_id`，无删除） |
| 静态校验 | `ast.parse` + `feature_version=(3,10)` 通过；14 处锚点每步 AST 校验 |

## 1. 四处修正

### 修 1a（mask_secret `keep[1]==0` 漏整串）
```diff
-    return "%s****%s(len=%d,sha8=%s)" % (s[:keep[0]], s[-keep[1]:], len(s),
-                                           _hashlib.sha256(s.encode()).hexdigest()[:8])
+    _tail = s[-keep[1]:] if keep[1] > 0 else ''
+    return "%s****%s(len=%d,sha8=%s)" % (s[:keep[0]], _tail, len(s),
+                                           _hashlib.sha256(s.encode()).hexdigest()[:8])
```
对现有调用中立（默认 `keep=(4,4)` 时 `keep[1]>0`，行为不变）。

### 修 1b（调用点改 `keep=(0,0)`）
```diff
-            rec['req_DevId'] = dv.strip()
+            rec['req_DevId'] = mask_secret(dv.strip(), keep=(0, 0))
-            rec['req_DeviceUniqueId'] = du.strip()
+            rec['req_DeviceUniqueId'] = mask_secret(du.strip(), keep=(0, 0))
```
产出 `****(len=9,sha8=a424da70)`，一个字符不露。

### 修 2（P4 三值判定：未知 ⇒ 退兜底，绝不建号）
```python
        ident = svc.identify(req)
        # [PATCH-PY-20261118-P4] 绝不凭未知 dev_id 建号：未知/无行一律退兜底账号
        try:
            _dev = (getattr(ident, 'dev_id', '') or '').strip()
            _fb = str(FALLBACK_DEV_ID)
            _exists = None
            if _dev:
                try:
                    _exists = svc.get_account_by_dev_id(_dev) is not None
                except Exception:
                    _exists = None                      # 未知
            if _exists is True:
                rec['acct_id_src'] = 'exact'
            else:
                try:
                    _fb_exists = svc.get_account_by_dev_id(_fb) is not None
                except Exception:
                    _fb_exists = None                   # 未知
                if _exists is False and _fb_exists is False:
                    rec['acct_id_src'] = 'create'       # 两者都确认不存在 ⇒ 真全新安装
                else:
                    ident.dev_id = _fb                  # 未知/或兜底存在 ⇒ 一律退兜底号
                    ident.dev_id_source = (getattr(ident, 'dev_id_source', None) or 'DevId') + '+retarget'
                    rec['acct_id_retarget'] = True
                    rec['acct_id_src'] = 'retarget-fallback'
        except Exception as e:
            rec['acct_id_src'] = 'resolve-err:' + type(e).__name__
            try:
                ident.dev_id = str(FALLBACK_DEV_ID)     # 兜底中的兜底
                rec['acct_id_retarget'] = True
            except Exception:
                pass
        acct = svc.get_or_create_account(ident)
```

### 修 3（env 校验 + 模块级求值一次）
```python
def _fallback_dev_id():
    v = (os.environ.get('BA_FALLBACK_DEV_ID') or '').strip()
    if v.isdigit() and 0 < len(v) <= 20 and int(v) > 0:
        return v
    return '314816420'


FALLBACK_DEV_ID = _fallback_dev_id()
```

### 修 4（relay `_frag` 提前到 if 之前，两处 relay 都改）
```diff
-    if isinstance(rec, dict) and not rec.get('req_frag_head'):
-        _frag = decoded.get('fragment') if isinstance(decoded, dict) else None
-        if isinstance(_frag, str):
+    _frag = decoded.get('fragment') if isinstance(decoded, dict) else None
+    try:
+        _FRAG_TLS.v = _frag if isinstance(_frag, str) else None
+        _FRAG_TLS.seq = id(rec)
+    except Exception:
+        _FRAG_TLS.v = None
+        _FRAG_TLS.seq = None
+    if isinstance(rec, dict) and not rec.get('req_frag_head'):
+        if isinstance(_frag, str):
             rec['req_frag_head'] = mask_secret(_frag[:300])
```
（`rl_request_json` 与 `req_builder` 两个调用方各一处，行为一致）

## 2. 自测：**19 PASS / 0 FAIL**

```
1     fragment 被解析
1b    req_devid_src=fragment
1c    req_devid_len=16 / sha8=8e9916c5
2     req_DevId 形态 ****(len=16,sha8=8e9916c5)（一个字符不露）
2b    不含原值任何片段
2c    rec 中无完整 fragment
2d    TLS 消费后清空
3     seq 不配对时不使用 TLS
5f    mask_secret('314816420', keep=(0,0)) → ****(len=9,sha8=a424da70)  不含原串
5f2   mask_secret('314816420', keep=(2,0)) → 31****(len=9,...)         不含原串
5d    BA_FALLBACK_DEV_ID ∈ {abc,-5,0,'',' '} → 全部回退 314816420
5d2   合法 env '777' → 生效
4a    真 dev 有行 → exact
4b    真 dev 无行 → retarget（dev_id_source=DevId+retarget）
5c    两者都无行 → create，且 ident.dev_id 仍是真 dev_id
5a    真 dev 查询抛异常 + 兜底存在 → **退兜底，不建号**
5b    两次查询都抛异常 → **仍退兜底，不建号**
4e    rec 中无 dev_id 明文（只有 acct_id_src / acct_id_retarget）
5     devid_on()=False 时仍写脱敏+诊断
```
复现：`python _patched\_selftest_patch.py`

## 3. 不变量核对

1. ✅ 真 dev_id 存在性**未知** ⇒ 一律退兜底号，绝不建号（5a/5b 用例）
2. ✅ 只有 `_exists is False and _fb_exists is False` 才建号（5c 用例）
3. ✅ 改完 `ident.dev_id` 后仍调 `get_or_create_account` ⇒ `_stamp_login` 不丢
4. ✅ 最外层 except 也把 `ident.dev_id` 拉回兜底号
