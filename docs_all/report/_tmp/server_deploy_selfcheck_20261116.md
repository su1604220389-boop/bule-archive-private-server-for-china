# 服务器依赖文件传送 + 只读自检报告

- 时间：2026-11-16 06:25 ~ 06:31（Asia/Shanghai）
- 目标机：`<SERVER_IP>`（root，Ubuntu 5.15.0-179-generic，Python **3.10.12**）
- 目标目录：`/www/wwwroot/bapatch/tools/`
- 方式：Windows OpenSSH 9.5p2 → `scp`（4 小文件一次 + ExcelDB.db 单独后台）
- 主机密钥：临时参数 `-o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL`，**本地 known_hosts 未改动**（前后 sha256 均为 `5eecdc3612feefc4c5b06c7dd3a3b372e32706bd7c3c827f1b1ed34dea2df7c4`，843 B）

## 1. 传送前勘察

`/www/wwwroot/bapatch/tools/` 已存在（`www:www 755`），含 100+ 文件（account_auth_probe.py 及大量 .bak/.pre_* 快照、cn_*.py、cn_wire.py、official_*_probe.py 等）。

**5 个目标文件全部 ABSENT**（无一存在，故无覆盖风险、无需报告既有版本）：

```
ABSENT /www/wwwroot/bapatch/tools/gen1017.py
ABSENT /www/wwwroot/bapatch/tools/specgen.py
ABSENT /www/wwwroot/bapatch/tools/official_spec.json
ABSENT /www/wwwroot/bapatch/tools/initial_state_rules.json
ABSENT /www/wwwroot/bapatch/tools/ExcelDB.db
```

线上 bridge 身份核对（只读）：

```
d5f27fcab6a897c88a8281fe9b2bd043924b68b5ca1c3ba4f60fd8649d1b814e  account_auth_probe.py
73445 bytes  root:root 644  2026-11-16 06:07:07
```

磁盘：`/dev/vda3 40G 24G 14G 64% /`（可用 14.4 GB，153 MB 拷贝余量充足）。

## 2. 传输结果 + 双侧 sha256 对照

| 文件 | 本地字节 | 服务器字节 | 本地 sha256 | 服务器 sha256 | 一致 |
|---|---:|---:|---|---|---|
| `gen1017.py` | 62,688 | 62,688 | `ad4e3ec99fe807d627e410b510af28dc639026a966579749bc6fd2bfd0096221` | `ad4e3ec99fe807d627e410b510af28dc639026a966579749bc6fd2bfd0096221` | ✅ |
| `specgen.py` | 22,794 | 22,794 | `a268f4a1c01994e7520e2cd138dcf2a5f1b885e6e6e1a1c00d70348b82fa173c` | `a268f4a1c01994e7520e2cd138dcf2a5f1b885e6e6e1a1c00d70348b82fa173c` | ✅ |
| `official_spec.json` | 958,494 | 958,494 | `028430a07f173211dbe69018d1201cd007f4838b136d6210f81195957f9afb1b` | `028430a07f173211dbe69018d1201cd007f4838b136d6210f81195957f9afb1b` | ✅ |
| `initial_state_rules.json` | 42,889 | 42,889 | `81e3790e094142fb7a1cc5fd0d533c7a801e2b5c731911aa2629e7ed855d4cb3` | `81e3790e094142fb7a1cc5fd0d533c7a801e2b5c731911aa2629e7ed855d4cb3` | ✅ |
| `ExcelDB.db` | 160,534,528 | 160,534,528 | `c49096aa6fdafee3c7bb4d5293039e1dafe1521c09c033bd25566aefae2cc5a9` | `c49096aa6fdafee3c7bb4d5293039e1dafe1521c09c033bd25566aefae2cc5a9` | ✅ |

5/5 完全一致，无一处不符。

传输明细：
- 4 个小文件（合计 3.06 MB）：一次 `scp`，约 2 s。
- `ExcelDB.db`（153 MB）：后台 `scp`，06:25:06 起、06:25:51 完成（约 45 s，≈3.4 MB/s），exit 0。
- 服务器侧 `ls`：全部 `-rw-r--r-- root:root`，mtime `2026-11-16 06:25`。

`find . -maxdepth 1 -newermt "2026-11-16 06:24"` 证实本次足迹**只有**这 5 个文件 + 目录 mtime（其余文件一个未动）：

```
06:25  160534528 ./ExcelDB.db
06:25      22794 ./specgen.py
06:25      42889 ./initial_state_rules.json
06:25      62688 ./gen1017.py
06:25     958494 ./official_spec.json
```

## 3. gen1017 只读自检

依赖定位证据（说明用的是刚传的这几个文件，不是别处的旧物）：

```
HERE            = /www/wwwroot/bapatch/tools
_SPECGEN_DIR    = /www/wwwroot/bapatch/tools
DATA[spec   ] = /www/wwwroot/bapatch/tools/official_spec.json        size=958494
DATA[rules  ] = /www/wwwroot/bapatch/tools/initial_state_rules.json  size=42889
DATA[exceldb] = /www/wwwroot/bapatch/tools/ExcelDB.db                size=160534528
```

`gen1017` 的路径解析在找不到 `work/ba/proto/...` 仓库布局时会回落到「与 gen1017 同目录」的扁平查找，因此在 `tools/` 平铺这 4 个文件即可，**无需设置 `BA_SPEC_PATH` / `BA_RULES_PATH` / `BA_EXCELDB_PATH` / `BA_SPECGEN_DIR`**。

自检输出（原样例命令，另加 `-B` 以免向 `__pycache__` 写 .pyc）：

```
35 {'inner': 83804, 'outer': 93307, 'wire': 124460}
```

对照期望：顶层键 **35** ✅、inner **83804** ✅、wire **124460** ✅（outer 93307 为随附信息）。
`[self-check exit=0]`，无 traceback、无 stderr。

只读性证据：`__pycache__/` 内容未变（最新仍是 `account_auth_probe.cpython-310.pyc` 06:07 与 `cn_wire...pyc` 05:39，**没有** gen1017/specgen 的 .pyc）；`account_auth_probe.py` sha256 仍为 `d5f27f...`、73445 B、mtime 未变；bridge 进程 `2529465 python3 account_auth_probe.py` 仍在运行。

## 4. 另外 3 个生成器

服务器 `/www/wwwroot/bapatch/tools/`：**三个全部不在**（未传、未找替代）。

```
ABSENT gen90004.py     → python3 -c "import gen90004"  → ModuleNotFoundError
ABSENT gen8000.py      → python3 -c "import gen8000"   → ModuleNotFoundError
ABSENT gen_simple.py   → python3 -c "import gen_simple"→ ModuleNotFoundError
```

本地 `work\ba\server\deploy\` 字节数：

| 文件 | 字节 | 本地 sha256 |
|---|---:|---|
| `gen90004.py` | **4,140** | `c1ca45ca8feba2625f9511b36db3fdf0191a00df2c97b810e061fc615d2dc236` |
| `gen8000.py` | **41,437** | `3159d3d515c0080cfed6a103efe366d0e84938482cad23c64e8c8b57e2c7e3fb` |
| `gen_simple.py` | **15,227** | `57e3a524e9a1716adfa8e76edf3e57966cf9c911ab3948a4ec3f8e3eca46f286` |

**依赖也不满足**（即使只传生成器也跑不起来，服务器上同样全缺）：

| 依赖 | 谁需要 | 服务器 |
|---|---|---|
| `dto90004.py` | gen90004（`import dto90004`） | ABSENT |
| `gen_common.py` | gen90004（`import gen_common as G`） | ABSENT |
| `spec_check.py` | gen8000（L560 懒加载）、gen_simple（L69 懒加载） | ABSENT |
| `8000_catalog.json` | gen8000 数据源 | ABSENT |
| `simple_payload.py` | gen_simple 数据源（本地 13,099 B） | ABSENT |
| `generator_registry.py` / `patch_preempt.py` | 配套 | ABSENT |

## 5. 开关文件现状（只读）

| 路径 | 状态 |
|---|---|
| `/www/wwwroot/bapatch/cn_preempt.txt` | **不存在**（`No such file or directory`）→ patch_preempt 处于"默认关" |
| `/www/wwwroot/bapatch/cn_bridge_exp.txt` | 存在，22 B，`root:root 644`，mtime 2026-11-14 04:13:55，内容：`decrypt+plain+http200\n` |

`/www/wwwroot/bapatch/` 下另有 `cn_bridge_exp.txt.bak.1794598994`（22 B）及若干 `cn_*.txt` 开关（`cn_bridge_mode`、`cn_canary`、`cn_field_patch` …），均未改动。

## 6. 磁盘剩余空间

```
/dev/vda3   40G   24G   14G   65%   /
可用：14,223,486,976 B（约 13.2 GiB）
```

（传输后由 14.4 GB → 14.2 GB，消耗即这 153 MB。）

## 7. 结论

**能。gen1017 现在可以在服务器上正常 build，且实测已 build 出 124,460 wire 的结果。**
`35 / inner 83804 / wire 124460` 三项与期望逐字一致，exit 0，没有任何 traceback。缺 `specgen.py` 导致的 `SystemExit(2)`（L130-133）路径已被排除；`official_spec.json` / `initial_state_rules.json` / `ExcelDB.db` 的 `raise SystemExit`（L1072/1082/1093）也全部不再触发。

遗留注意（与本次任务无关，供后续排期）：
1. `gen1017.py` 的 **CLI** 默认 `--spec-check=True`，会 `import spec_check`（L1264），服务器上**没有** `spec_check.py` → 直接在服务器跑 `python3 gen1017.py --out ...` 会在最后一步 `ModuleNotFoundError`。**`build()` 路径不受影响**（本次自检正是 build）。若以后要跑 CLI，需再传 `spec_check.py`，或加 `--no-spec-check`。
2. 线上 `account_auth_probe.py` 目前**仍无任何 `gen1017` 引用**（`grep -n gen1017` 无命中），即接线补丁尚未 apply —— 文件已就位，但 bridge 还不会调用它。
3. 另外 3 个生成器及其依赖（详见 §4）需另行成组传输；`spec_check.py` 会被三者中的两个共用，建议一次带齐。
