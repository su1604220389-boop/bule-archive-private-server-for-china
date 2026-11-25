# patch_1017（Account_LoginSync）只读验证报告

- 时间：2026-11-16 06:18–06:30 (+08:00)
- 结论：**补丁本身 PASS，可以安全 apply；但现在 apply 等于零效果 —— gen1017 的 5 个依赖件在服务器上一个都没有。**
- 全程只读：未 `--apply`、未重启、未改任何线上文件/脚本。所有写操作只发生在
  `work\ba\server\deploy\_scratch\probe_1017_ro\` 与 `%TEMP%`。

---

## 1. 脚本常量（`work\ba\server\deploy\patch_1017.py`，32,071 B / 773 行 / sha256 B5EB6D97…）

| 常量 | 实际值 |
|---|---|
| `DEFAULT_TARGET` | `/www/wwwroot/bapatch/tools/account_auth_probe.py` |
| `DEFAULT_MODE_FILE` | `/www/wwwroot/bapatch/cn_1017_mode.txt` |
| `ANCHOR_A` | `class Handler(http.server.BaseHTTPRequestHandler):` |
| `ANCHOR_B` | `        if num in (1019, 1017):`（8 空格缩进） |
| `GEN1017_NAME` | `gen1017.py` |
| `MARK_BEGIN` / `END` | `# >>> BA-1017-DYNAMIC-PATCH v1 …` / `# <<< BA-1017-DYNAMIC-PATCH v1 <<< …` |

`gen1017.py` 同目录存在：62,688 B / sha256 ad4e3ec9…

## 2. 线上目标文件（只读确认）

```
-rw-r--r-- 1 root root 73445 Nov 16 06:07 /www/wwwroot/bapatch/tools/account_auth_probe.py
sha256 d5f27fcab6a897c88a8281fe9b2bd043924b68b5ca1c3ba4f60fd8649d1b814e
1777 行
备份：account_auth_probe.py.bak.20261116_060707  = 54,026 B
      account_auth_probe.py.pre_24v3.20261116_060707 = 54,026 B
进程：pid 2529465，启动 Mon Nov 16 06:07:10，cwd=/www/wwwroot/bapatch/tools
开关：/www/wwwroot/bapatch/cn_1017_mode.txt 不存在 → cn_1017_mode() 默认 'dynamic'
```

拉到本地副本逐字节一致（73,445 B / d5f27fca…），所有 verify 都跑在这份副本上。

## 3. `--verify` 逐项

| 项 | 实际输出 |
|---|---|
| 目标文件大小 / sha256 | 73445 B / d5f27fca…9b814e |
| 语法 | ok |
| marker begin/end | begin=0 end=0 → **未打补丁** |
| 锚点 A | **第 1139 行**（存在） |
| 锚点 B | **第 1345 行**（存在） |
| 旧分支校验 | 旧 1017/1019 分支 7 行逐字匹配 |
| gen1017 顶层键 / 子回包 | 35 / 26 |
| inner 字节 / wire 字节 | 83,639 B / 124,248 B（固定 now） |
| gen1017 自检 | PASS |
| 运行时开关 | 'dynamic' |
| **最终结论** | **PASS**（exit 0） |

## 4. 核心问题：锚点还在吗 → **在，不需要改锚点**

`patch_24000_v3` 只插入自己的模块级块，没有改 `class Handler(...)` 这一行、也没有动
`if num in (1019, 1017):`，所以两个锚点原样保留，只是行号被推移：

| | `_bridge_ref` 基线 46,568 B | 线上 73,445 B |
|---|---|---|
| ANCHOR_A | 485 | **1139** |
| ANCHOR_B | 696 | **1345** |

## 5. `--dry-run`（在副本上跑）

- 原文 1,777 行 → 新文 1,834 行：**+57 行，两段纯插入，无删改**
- 73,445 B → 76,098 B（模拟 sha256 = b9e248879051681fc2daa9e375d3023dafd17afb14098c9ccc0f53c2da9a6f0d）

| 插入块 | 位置 | 行数 |
|---|---|---|
| A（module level：`cn_1017_mode` / `_gen1017_import`） | 插在**第 1139 行之前**（即第 1138 行 `return cn_cipher.wrap_packet(inner), frag` + 2 空行之后） | 26 |
| B（1017 dispatch） | 插在**第 1345 行之前**（即 24000-v3 块 `return _ba24000_send(...)` 之后） | 31 |

hunk 1 上下文：
```
     return cn_cipher.wrap_packet(inner), frag
 
 
+# >>> BA-1017-DYNAMIC-PATCH v1 ...
...
+# <<< BA-1017-DYNAMIC-PATCH v1 <<<  (module level)
 class Handler(http.server.BaseHTTPRequestHandler):
     protocol_version = 'HTTP/1.1'
```
hunk 2 上下文：
```
             rec['gen_v'] = 'v3'
             rec['fallback'] = 'dynamic-24000'
             return _ba24000_send(name or 'Academy_GetInfo', obj, rec)
+# >>> BA-1017-DYNAMIC-PATCH v1 ...
...  (if num == 1017 and cn_1017_mode() != 'legacy': ... return 200, _wire, ...)
+# <<< BA-1017-DYNAMIC-PATCH v1 <<<  (1017 dispatch)
         if num in (1019, 1017):
             obj = {"Protocol": 1019, ...
```

## 6. `--selftest` 与自定义彩排

`python patch_1017.py --selftest` → **PASS**，但它跑的是 `_bridge_ref` 基线（46,568 B），
**不是线上这份 73,445 B**，覆盖价值有限。

所以另做了一次「线上文件临时副本」彩排（`_scratch\probe_1017_ro\live_rehearsal.py`）：

```
apply      : 73,445 B → 76,098 B (+57 行)，sha b9e24887…
apply 再来  : 幂等 True
verify     : marker 2/2 已打补丁；锚点 A 1165 / B 1402；旧分支 7 行逐字匹配；PASS
prove-dispatch: 三元组 ok / 35 键 / outer requestid == inner RequestId
                wire 124,460 B；legacy 落到旧分支 True；gen1017 抛异常兜底 True
rollback   : 删 2 段 marker，1834 → 1777 行，sha 回到 d5f27fca…（与线上逐字节相同）
再 verify   : PASS
```

→ **apply 可逆性已被实证：rollback 后与线上文件逐字节相同。**

## 7. 额外关键验证：1017 现在真的会走到 1345 行

线上日志 `logs/api_all_requests.log:323`（最后一次真实 1017，2026-11-16 06:12:48，
`POST /api/account/loginsync`，UA=BestHTTP/2）的 rec：

```
protocol_name : Account_LoginSync
decrypt_json_none: true
fallback      : generic-envelope
gen_protocol  : 1017
gen_kind      : loginsync-1017        ← 旧分支 1345 执行了
enc_inner_keys: 10                    ← 旧 9 键 + RequestId
enc_plain_len : 386
enc_body_len  : 576                   ← 客户端收到的那 576 B
resp_len      : 576
known_other_upgraded: true            ← 证明走的是 1755 行 _generic_protocol_response
```

结论：1017 **没有**被 1749 行 path D 的 min-envelope 截胡（`req_Hash` 不存在），
插入块位置在真实代码路径上；返回的三元组由 `_handle` 1214–1216 行 `_send(code, resp, ctype, opts)`
消费，`_send_opts(close=True)` 也会被生效。**补丁会真的改变 1017 行为（前提是依赖件到位）。**

## 8. 阻塞项：gen1017 依赖件在服务器上全缺

`/www/wwwroot/bapatch/tools/` 里 **没有** `gen1017.py` / `specgen.py` /
`official_spec.json` / `initial_state_rules.json` / `ExcelDB.db`，进程环境也没有 `BA_*` 变量。

需要一起部署（本地路径 / 字节 / sha256）：

| 文件 | 字节 | sha256 |
|---|---|---|
| `work\ba\server\deploy\gen1017.py` | 62,688 | ad4e3ec99fe807d627e410b510af28dc639026a966579749bc6fd2bfd0096221 |
| `work\ba\server\prototype\specgen.py` | 22,794 | a268f4a1c01994e7520e2cd138dcf2a5f1b885e6e6e1a1c00d70348b82fa173c |
| `work\ba\proto\official_spec.json` | 958,494 | 028430a07f173211dbe69018d1201cd007f4838b136d6210f81195957f9afb1b |
| `work\ba\proto\initial_state_rules.json` | 42,889 | 81e3790e094142fb7a1cc5fd0d533c7a801e2b5c731911aa2629e7ed855d4cb3 |
| `work\ba\data\ExcelDB.db` | 160,534,528 | c49096aa6fdafee3c7bb4d5293039e1dafe1521c09c033bd25566aefae2cc5a9 |

五个文件都放进 `tools/` 即可，无需设环境变量（gen1017 会在自身目录按裸文件名回退查找）。
注意：服务器上 `/www/wwwroot/ba_srv/Resources/{Dumped,Downloaded}/ExcelDB.db` 是
**311,083,008 B**，与本地验证用的 160,534,528 B 不是同一个文件，不要拿来替代。

**危险点**：`gen1017.py` 的 `SystemExit`（specgen 缺失时 line 133；数据缺失时
`_load_spec/_load_rules/_open_master` 1072/1082/1093）不是 `Exception` 的子类，
补丁里 `except Exception as _e1017` **捕获不到** → 1017 会直接抛 traceback / 断连，
比现在的 576 B 更糟。**五件必须同时到位，绝不能只传 gen1017.py。**

若五件都没传（当前状态）：`_gen1017_import()` 抛 `ModuleNotFoundError`（属 Exception）→
被捕获 → 走旧 576 B 分支 → 行为不变、安全但无效。

## 9. 能不能安全 apply

- **机制上：可以。** verify PASS、+57 行纯插入、幂等、dispatch 证明 PASS、rollback 逐字节还原、
  旧分支与 1019 完全未动、gen1017 任何 `Exception` 都会静默回落。
- **效果上：现在 apply 是无效的**，必须先补齐 §8 的五个文件。
- **生效还需要重启 bridge 进程**（模块启动时加载）——本轮禁止，未做。
- 回滚两条路：`--legacy` 写开关文件（**免重启**、立刻回到 576 B）；`--rollback` 删 marker（需重启，逐字节还原）。

## 10. 体积口径（不是缺陷）

官方 246,808 B 是「C 官方状态回放」（167,287 inner）那一档；新号是另一档：
固定 now = 83,639 / 124,248，真实时钟 = 83,804 / **124,460**（本次实测 build 3 次一致）。
顶层键仍是 35/35 与官方 spec 对齐。所以 124 KB ≠ 246 KB 是账号数据量差异，
但「客户端是否接受 ~124 KB 的新号响应」只能在设备上验证，无法离线证明。

## 11. 其他可疑 / 需要注意

1. **SSH 主机密钥变了**：known_hosts（2025-09 写入）的 ED25519 指纹是
   `SHA256:o01m9fFbYmwBR/0rdooApgpp04azonuHsWxR0JDcEAo`，本次服务器给的是
   `SHA256:dTKptFoQMPWQpaX6STUccIdf50VYKIcyPWyTaQCcuFQ`（ECDSA 也冲突）。
   我没有改 known_hosts，用了 `%TEMP%` 下的临时 known_hosts 连接。建议确认这台机器
   是否重装/换过密钥。
2. **文档口径过期**：patch_1017.py 文档说旧 1017 是「inner 216 / wire 492」，线上日志实测是
   **inner 386 plain / wire 576**（10 键）。不影响补丁逻辑，但别拿 492 当回滚验收值。
3. **`--verify` 的 PASS 有歧义**：未打补丁状态也返回 PASS。当前是「未打补丁的 PASS」。
4. **开关文件不存在 = dynamic**：apply + 重启后 1017 会立刻走动态；若想先保守，先写 `legacy`。
5. **性能**：`build()` 每次请求都会新开 160 MB 的 ExcelDB（master 无缓存），实测
   首次 12 ms / 后续 4.5–5 ms，登录一次一次，可接受。
6. `--selftest` 测的是 `_bridge_ref` 基线而非线上文件，容易给人「已验证」的错觉。

## 12. 建议执行顺序（待批准，本轮未做）

1. 传 §8 五个文件到 `/www/wwwroot/bapatch/tools/`（160 MB ExcelDB 走压缩传输）。
2. 服务器上只读自检：`cd /www/wwwroot/bapatch/tools && python3 -c "import gen1017; o=gen1017.build({'server_id':10015354380},None,request_id='00000000-0000-4000-8000-000000000000'); print(len(o), gen1017.measure(o))"`
   → 期望 `35 {'inner': 83804, 'wire': 124460}`。
3. `python3 patch_1017.py --verify --target /www/wwwroot/bapatch/tools/account_auth_probe.py`（期望 PASS + marker 0/0）
4. `--dry-run` 复核 +57 行。
5. `--apply`（自动备份 + 原子写 + 打后语法检查）。
6. 重启 bridge，登录，看日志 `gen_kind=loginsync-1017-dynamic` / `enc_inner_keys=35` / `resp_len≈124460`。
7. 若客户端仍报错：`--legacy` 免重启回到 576 B，再查 `gen1017_err`。
