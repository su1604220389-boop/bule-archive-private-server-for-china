# BATCH DEPLOY 2026-11-17 —— 三批清单 / 执行记录 / 验收

执行者：srv-ops
目录：`_blackout\srv\`
本文覆盖：批次 1（已完成）、批次 2/3（方案，待执行）

---

## 批次 1：桥接三合一（已完成，验收通过）

### 1-1 补丁清单
| # | 标记块 | 改动 | 开关 |
|---|---|---|---|
| 1 | `BAPATCH-DEVID v1` | `_req_dict()` 里把 `DevId/DeviceUniqueId` 缓存进 rec；`:108` 兜底字典补 `DeviceUniqueId` | `cn_devid.txt` |
| 2 | `BAPATCH-90011 v1` | `90011` 加进 `RL2_HANDLED`（自造，不转发） | 无（随 `cn_relay_known.txt`） |
| 3 | `BAPATCH-DEDUP v1` + `v1 RELAYPATH` | 29001 订单短时去重（同单回放缓存响应） | `cn_dedup.txt` / `cn_dedup_window.txt` |

### 1-2 文件与备份
```
改前 sha256 : ade3917cab391de3d782decbdceda1d71556a9ee7e2487be869afebcd2f73807  (147,? B)
备份        : /www/wwwroot/bapatch/tools/account_auth_probe.py.batch1.bak.20261117_202722
              sha256 ade3917cab391de3d782decbdceda1d71556a9ee7e2487be869afebcd2f73807
改后 sha256 : **8d43dca2ca530e5c20c2fa6c52ead5f1e9c666ed3f5fadf9c8160481ca43d3b1**  (157,724 B)
AST_OK / PY_COMPILE_OK / Traceback = 0
桥 pid      : 2633742（9097 LISTEN）
```
**回滚（一行）**
```bash
cp -a /www/wwwroot/bapatch/tools/account_auth_probe.py.batch1.bak.20261117_202722 \
      /www/wwwroot/bapatch/tools/account_auth_probe.py && pkill -f 'python3 account_auth_probe.py' && \
  (cd /www/wwwroot/bapatch/tools && setsid nohup python3 account_auth_probe.py >> /www/wwwroot/bapatch/logs/api_probe.out 2>&1 &)
```
**分项软回滚（不用重启）**：`echo 0 > /www/wwwroot/bapatch/cn_devid.txt` / `echo 0 > /www/wwwroot/bapatch/cn_dedup.txt`

### 1-3 自测（20:28–20:31，合成请求）
| 测试 | 结果 | 证据 |
|---|---|---|
| T1 DevId 接线 | **PASS** | `acct_svc='on'`、`req_DevId='999888777'`、`acct_server_id=10000000002`（新号）、`accounts.db` 3 行、新增 `(10000000002,'999888777','老师0003')` |
| T2 90011 | **PASS** | `relay2_fallthrough='handled-90011'`（未转发）、响应 536 B |
| T3 29001 去重 | **PASS** | 第 2 次 `dedup_hit=True`、`ms` 从 283 → **3 ms**、响应**逐字节相同**（448 B） |

**验收判据对照**
```
① acct_svc.log 不再出现 fallback to hardcoded  -> 20:28 之后无新 fallback 行（最后一条 18:37）
② acct_server_id 出现多个不同值                -> 10000000002 出现（此前只有 10000000000/1）
③ accounts.db 行数随测试卡增长                 -> 2 -> 3
```

### 1-4 如实记录：过程问题
1. **第一次 apply 失败**：`fix_batch1.py` 被 PowerShell `Set-Content` 写坏（BOM/编码），`python3` 报
   `SyntaxError: invalid character '：' (U+FF1A)`，**代码未被修改**（sha 仍 ade3917c），但当时已完成一次重启（**空重启**，行为不变）。
2. **dedupe 首版落点错**：`dedup_key` 用 `rec['req_frag_head']`，而该字段在 relay 解码前为空 → 不命中。已改为
   `BAPATCH-DEDUP v1 RELAYPATH`：在 `_rl2_relay_once` 内、`post_gateway` 之前用**真实请求 dict**（`PurchaseOrderId` 等）做键，命中即回放。
3. 因此**实际重启 3 次**（20:27 空重启、20:28 批次 1、20:31 relaypath），不是计划的 1 次。

### 1-5 测试残留
`accounts.db` 多出一条测试账号：`server_id=10000000002, dev_id='999888777', nickname='老师0003'`（无角色/无进度）。
如需清理，按"① 拉本地 ② sha256 ③ 授权 ④ 删除"四步走；**默认保留**（不删除）。

---

## 批次 2：LoginSync 修复（方案，待执行，需重建 Shittim）

| # | 改动 | 位置 | 依据 |
|---|---|---|---|
| 1 | `MemoryLobbyDBs` 补 `AccountServerId` | `AccountHandler.cs:426-429`（用 `ToMapList(_mapper)`，映射侧补字段） | 官方 HAR：`{"Type":8,"ParcelInfos":null,"AccountServerId":10015354380,"MemoryLobbyUniqueId":13010}` |
| 2 | `BillingPurchaseListByNexonResponse` → `...ByYostarResponse` | `AccountHandler.cs:495/543` + `Utils/Loaddata.cs:81` + DTO | **官方 HAR 顶层键实测就是 `BillingPurchaseListByYostarResponse`**（35 键清单已核对） |
| 3 | `MomotalkOutlineResponse` → `MomoTalkOutLineResponse` | `AccountHandler.cs:472`（属性名/序列化名） | 官方 HAR 键为 `MomoTalkOutLineResponse` |
| 4 | 去掉 `StaticOpenConditions` | `AccountHandler.cs:146/589` | 官方 HAR **无此键** |
| 5 | 24 子响应补 4 个信封字段 | 统一响应封装处 | 官方每个子响应都带 `Protocol/SessionKey/ServerTimeTicks/ServerNotification/RequestId`（已在 `CafeGetInfoResponse` 等 4 个样本上验证） |

**改名复核结论：该改。** 我上一轮"不用改名"的判断是错的（当时依据是客户端的 DTO 类名，而**序列化键名以官方 HAR 为准**）。

**§5 改动量评估**：`ResponsePacket` 基类（`Schale/MX/NetworkProtocol/Packet.cs:45`）已有这些字段；子响应在 `AccountHandler` 里是直接 `new XxxResponse{...}` 赋给父对象，**没有统一填充点**。
最小改法：在 `AccountLoginSync` 组装完成后、`return` 之前，遍历 24 个子响应对象，逐个填 `SessionKey/ServerTimeTicks/ServerNotification/RequestId`（**1 处循环，约 12 行**）；前提是这些属性在基类上可写。**这需要先在本地反射确认属性可写性**，再决定是否并入批次 2。

---

## 批次 3：上游删角色守卫（方案，待执行）

```
上游：Services/ExcelTableService.cs:186  public bool IsTableComplete<T>()
      AccountHandler.cs:381  if (_excelService.IsTableComplete<CharacterExcelT>()) { ... RemoveRange ... }
本地：AccountHandler.cs:377  db.Characters.RemoveRange(phantomCharacters);   ← 无守卫，无条件执行
```
M1：整方法复制 `IsTableComplete<T>()`；M2：把本地 377 行那一段包进守卫。
**DLL 可并入批次 2 一起部署。**
