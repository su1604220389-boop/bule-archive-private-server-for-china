# 90004 Management_Data 结构修复部署（D90004）

- 时间：2026-11-19 02:12（Asia/Shanghai）｜ 执行：srv-ops
- 目标：把桥里写死的 90004 桩（9 个业务键平铺在信封层、GachaProbabilityDisplay=false 等）改成官方的
  **6 层信封 + `Data` 外壳 + 9 个业务键**
- **最终判定：部署成功 · 31/31 检查 PASS · 保持新版本（KEEP）**

## 1. 线上基线（改前，实测）

```
/www/wwwroot/bapatch/tools/account_auth_probe.py
  -rw-r--r-- 1 root root 222,539 B   Nov 19 00:49
  md5    = da07749d63487ce28ce8d571853b037f
  sha256 = fd6ba5d8452e1cf8be3d6df1637fd5f1e7c281492be04c935dee711f3a002ff3
cn_bridge_exp.txt  = decrypt+plain+http200
cn_bridge_mode.txt = bridge
_ba_state/90004_ops.json ：**改前不存在**
```

## 2. 补丁与数据

| 文件 | 说明 | sha256 |
|---|---|---|
| `_p90004_bundle/patch_90004.py` | 补丁器 | `c94bae46…` |
| `_p90004_bundle/90004_ops.json` | 运营数据（Notices 6 / Events 14 / Banners 7 / Gacha 12） | **`938ae90855b5fa5fa11342854f2e0f28e7130b466c303621151685efc06107fb`** ✅ 与要求一致 |
| `_ba_state/90004_ops.json` | 安装到线上的位置 | 同上 ✅ |

> 按约束没有推本地的"已打好补丁的桥文件"，而是**用服务器上线上真身的副本**（`cp -a` → `./live.work.py`）打的补丁。

## 3. 体检结果（部署前 + 部署后）

**preflight（只读，改前）**
```
90004 branch  `if num == 90004:`           OK   line 3244
   branch: 23 lines / 16 quoted keys / has Data=False      ← 正是要修的问题
branch 以 _cn_send_envelope 收尾              OK
def _cn_send_envelope(  / rid = str(_uuid.uuid4()) / pick_requestid(rec) / SESSION = Session() / import json   OK
VERDICT: READY —— 5 个锚点齐全
```

**打完补丁（`.new` 副本上）**
```
patch_90004.py --apply  → 结果: PASS（outer_requestid: synced）
patch_90004.py --verify → 结果: PASS（inline_data_keys=9 ｜ inline_inner_bytes=420 ｜ inline_dirty_input=PASS ｜ outer_requestid: synced）
check_patch_90004.py    → RESULT: PASS
ast.parse(...)          → ast OK
grep -c 'if num == 90004:' → 1
```
部署后分支起始行 **3408**，分支头即新逻辑（`Data` 外壳 + 9 键 + `_sk9/_rid9/_t9`）：
```python
if num == 90004:
    from datetime import datetime as _d9
    import uuid as _uuid9
    _sk9 = getattr(SESSION, 'session_key', None) …
    _rid9 = pick_requestid(rec) or str(_uuid9.uuid4())
```
> 说明：我最初用 `grep` 统计"旧 16 键是否归零"时把分支范围截到 4073 行（越过了分支边界，含后续函数），
> 因此 `StaticOpenConditions/MissionProgressDBs` 等仍有计数；**权威判据是 `verify_90004.py` 的
> 「无旧 16 键多余额外键 = 无」+ `check_patch_90004.py RESULT: PASS` + `if num == 90004:` 仅 1 处**。

## 4. 覆盖与重启

```
install -m 644 ./live.work.py /www/wwwroot/bapatch/tools/account_auth_probe.py
线上 md5 = 891178d6ba9647d27a1d8b2f5d7c2d64（改后）
kill old pid 2790794 → cd /www/wwwroot/bapatch/tools && umask 007 && setsid nohup python3 account_auth_probe.py
**9097_UP 耗时 1,033 ms ｜ 实例数 = 1**
```

## 5. 验证（verify_90004.py，31 项）

```
POST http://127.0.0.1:9097/api/management/data  (417 B)
  -> HTTP 200 / **14,016 bytes** / text/plain
解码: cn_wire（plain 10,072 B / inner 6 键）

[PASS] HTTP 200                                  14016 bytes
[PASS] 顶层键集合（6 键）                          got=6 ['Protocol','SessionKey','ServerTimeTicks','ServerNotification','RequestId','Data']
[PASS] 顶层键序（官方 10/10 稳定）                  Protocol → SessionKey → ServerTimeTicks → ServerNotification → RequestId → Data
[PASS] Protocol == 90004                         got=90004 (int)
[PASS] SessionKey 形状                            {'AccountServerId': 0, 'MxToken': ''}
[WARN] SessionKey 非空                            AccountServerId=0 MxToken=空（bridge 尚未登录过账号，不影响结构）
[PASS] ServerTimeTicks 合理                       got=639306511604258110（与本机 now 差 -0.2 s）
[PASS] ServerNotification == 0                   got=0
[PASS] RequestId 是 uuid                          got='277b9be3-483f-4997-8987-a1d37e8c80d3'
[PASS] outer requestid == inner RequestId        outer == inner
[PASS] Data 是 dict（不是 null/缺省）              9 键
[PASS] Data 键集合（9 键）                         ['Notices','Events','Issues','Banners','GachaProbabilityDisplay','GuidePopup','GachaPeriodDisplay','RaidPeriodDisplay','Survey']
[PASS] Data 键序（官方 10/10 稳定）                Notices → Events → Issues → Banners → GachaProbabilityDisplay → GuidePopup → GachaPeriodDisplay → RaidPeriodDisplay → Survey
[PASS] Data.Notices 条数                          6 条（期望 6）
[PASS] Data.Events 条数                           14 条（期望 14）
[PASS] Data.Issues 条数                           0 条（期望 0）
[PASS] Data.Banners 条数                          7 条（期望 7）
[PASS] Data.GachaProbabilityDisplay 条数          12 条（期望 12）
[PASS] Data.GuidePopup 条数                       0 条（期望 0）
[PASS] Data.GachaPeriodDisplay is null           got=None
[PASS] Data.RaidPeriodDisplay is null            got=None
[PASS] Data.Survey is null                       got=None
[PASS] Data 逐字节（紧凑 JSON）                    9432 B (sha abc695f8f61deb60)
[PASS] 无旧 16 键多余额外键                        无
[PASS] GachaProbabilityDisplay/GuidePopup 是 list 都是 list
---------------------------------------------------------------------------------
31 checks / FAIL=0 / WARN=1
RESULT: PASS —— 90004 已是官方 6 层 + Data 9 键结构，与 expected_90004.json 一致
```

**人工复核（脚本独立解一遍）**
```
inner.keys = ['Protocol','SessionKey','ServerTimeTicks','ServerNotification','RequestId','Data']
有 Data 外壳 = True
Data.keys   = ['Notices','Events','Issues','Banners','GachaProbabilityDisplay','GuidePopup','GachaPeriodDisplay','RaidPeriodDisplay','Survey']
Notices = 6 ｜ Events = 14 ｜ Banners = 7
GachaProbabilityDisplay 类型=list 条数=12
GachaPeriodDisplay = None ｜ RaidPeriodDisplay = None
GuidePopup 类型 = list
含 SessionKey = True ｜ 含 RequestId = True ｜ 含 Survey = True
```

## 6. 登录链路回归（同一时刻）

```
① Account_Auth(1002)：HTTP 200 ｜ inner.Protocol=1002 ｜ 无 ErrorCode ｜ 含 SessionKey
② LoginSync(1019)：HTTP 200 ｜ **586,907 B** ｜ inner.keys=33 ｜ **ShopRecruits = 529 条**
   SessionKey = {"AccountServerId":4,"MxToken":"d1507dc8-…"} ｜ ServerNotification = None
③ Mail_Check(7001)：HTTP 200 ｜ ServerNotification = 8
SELFCHECK = PASS
```

## 7. 桥侧记账（新分支确实生效）

```
management-90004-official 条数 = 1
t=2026-11-19 02:12:40  path=/api/management/data
  gen_kind                = management-90004-official
  gen_protocol            = 90004
  gen_90004_data_keys     = 9
  gen_90004_lists         = {'Notices': 6, 'Events': 14, 'Issues': 0, 'Banners': 7, 'GachaProbabilityDisplay': 12, 'GuidePopup': 0}
  gen_90004_bytes         = 9215
日志异常：无
```

## 8. 备份与回滚

```
备份目录：/root/D90004_20261119_021229/
   account_auth_probe.py   ← 改前（222,539 B / md5 da07749d… / sha256 fd6ba5d8…）
   BEFORE.txt              （md5 + sha256 + 字节数）
   ROLLBACK.sh             （还原桥 → 若备份里有 ops 则一并还原、否则删除 ops → cd tools 重启 → 轮询 9097 → 打印 md5）
```

**ROLLBACK.sh 完整路径：**
```
/root/D90004_20261119_021229/ROLLBACK.sh
```
（改前 ops 文件不存在，因此回滚会 `rm -f _ba_state/90004_ops.json`）

## 9. 未触碰

nginx / 数据库 / `Shittim-Server.dll`（仍 `160c3e15…`）/ `Data/*.json`（卡池仍 `3ac8385d…` 529 条）/ `ClientItemIds.txt` —— 全部未动。

## 10. 备注

- 唯一 WARN 是 `SessionKey` 为空（`AccountServerId=0 / MxToken=""`），因为桥重启后还没跑过登录；
  客户端真实登录后会变成真实值，不影响结构判定。
- 新分支读不到 ops 文件时会退回"列表全空 + 3 个 null"的合法新形状（此时 verify 会 FAIL 提示），
  本次 ops 已就位且校验通过，条数为 6/14/7/12/0。
