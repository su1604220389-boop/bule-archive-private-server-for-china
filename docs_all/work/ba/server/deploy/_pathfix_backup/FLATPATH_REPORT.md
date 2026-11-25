# 生成器扁平目录（/www/wwwroot/bapatch/tools/）路径发现改造 — 报告

日期：2026-11-16
本机仓库：`C:\Users\su\Desktop\大肥鱼项目\BAServer`
线上：`/www/wwwroot/bapatch/tools/`（无 `work/ba/...` 层级）

---

## 1. 现状分析：三个 patch 是怎么 import 生成器的

| 补丁 | 怎么拿生成器 | 是否已经处理路径问题 |
|---|---|---|
| `patch_90004.py` | 模块级 `sys.path.insert(0, HERE)` + `import gen_common as G`；`dto90004.py` 是 `open()` 读源码后**内联**进 bridge（`DTO_SRC`） | **否**。只解决 `import gen_common` 的模块路径，不解决 `gen_common` 内部的数据文件路径；而且它**不 import `gen90004`、不跑生成器** |
| `patch_8000.py` | `build_catalog_text()` 内 `sys.path.insert(0, HERE)` → `import gen8000`，整段包在 `try/except` 里，失败就回落到同目录 `8000_catalog.json` 并标注 `gen8000 不可用: ...` | **否**。只解决模块路径，且把失败吞成 fallback（线上扁平布局会静默用现成 catalog），不解决 `P_SPECGEN/P_EXCELDB/P_PROTO` |
| `patch_simple.py` | `simple_payload.py` 是 `open()` 读源码后内联；`--verify` 里用**它自己**的 `ROOT` 推 `SPECGEN_PATH/SPEC_PATH` 加载 specgen 做口径比对 | **否**。这些路径是补丁自己的（只在仓库布局有意义），它**不 import `gen_simple`**，与生成器路径无关 |

**结论：三个补丁都没有替生成器做数据文件发现 → 必须改生成器。**
（线上实际用法是 `cd /www/wwwroot/bapatch/tools && python3 -B -c "import genNNNN; ...build()"`，直接踩生成器自己的 `ROOT`。）

另外发现一个必须一起处理的点：`gen8000.build_response()` 里是 `sg.Spec()`（不传路径），
用的是 `specgen.py` **自己的** `SPEC_PATH = ROOT/work/ba/proto/official_spec.json`。
即使我们找到了 `official_spec.json`，引擎仍会去开错误路径。`specgen.py` 在禁止修改清单里，
所以改为把发现到的路径**显式传进去**：`sg.Spec(P_SPEC)`（1 行）。

---

## 2. 改动清单（只动路径发现，未动任何生成/序列化逻辑）

备份：`work/ba/server/deploy/_pathfix_backup/*.orig`（改动前的原文件，sha256 与线上原版一致）
线上备份：`/www/wwwroot/bapatch/tools/<file>.pre_flatpath.20261116_064112`

| 文件 | 改前 | 改后 | 行变化 | sha256 改前 | sha256 改后 |
|---|---|---|---|---|---|
| `gen_common.py` | 15,910 B / 401 行 | 17,773 B / 446 行 | +50 / -5 | `847c5f268cc899ed1d07b43adee2c482483469e46215e29fe6a97b6949e4fbf7` | `1998eb226194ec3893e1fc4b8e035a8d64fa6c583302ca147b0f15b13d577d92` |
| `gen8000.py` | 41,437 B / 886 行 | 43,589 B / 936 行 | +55 / -5 | `3159d3d515c0080cfed6a103efe366d0e84938482cad23c64e8c8b57e2c7e3fb` | `9432e4ee1b5e1ba527516638d467181f074145845bd844889acabdd46c867598` |
| `gen_simple.py` | 15,227 B / 327 行 | 17,315 B / 376 行 | +54 / -5 | `57e3a524e9a1716adfa8e76edf3e57966cf9c911ab3948a4ec3f8e3eca46f286` | `93461a082c043af5b6f9d7d4377b91bf64f48af75b12b3b08ff7cd75c8b3d8a1` |
| `gen90004.py` | 4,140 B / 93 行 | 4,415 B / 97 行 | +5 / -1 | `c1ca45ca8feba2625f9511b36db3fdf0191a00df2c97b810e061fc615d2dc236` | `67128f8d541315d9e1fc467571ecf4f054d71d16f420d1410095e90affba1492` |

改动内容（全部在「路径发现」这一处）：

1. **`gen_common.py`**：`PROTO_DIR / SPEC_PATH / DTO_EXTRA_DIR / EXCELDB_PATH / DECODED_DIR`
   由写死的 `ROOT/work/ba/...` 换成 `_find_path()` 发现结果；`ROOT` 本身不动。
2. **`gen8000.py`**：`P_PROTO / P_SPECGEN / P_EXCELDB / P_CAPTURE` 同上换法，新增 `P_SPEC`
   （`official_spec.json` 本体），并把 `build_response()` 的 `sg.Spec()` 改成 `sg.Spec(P_SPEC)`。
3. **`gen_simple.py`**：`PROTO_DIR / SPEC_PATH / RULES_PATH / DECODED_DIR / SPECGEN_PATH` 同上换法。
4. **`gen90004.py`**：只改 `DEFAULT_OUT` —— 有 `<repo>/report` 时保持原样；
   扁平部署没有 `report/` 时回落到 `HERE/out/t90004.json`（原来线上不给 `--out` 会试图写 `/report/_tmp`）。

查找顺序（照抄 `gen1017.py`，环境变量名完全相同）：

```
环境变量（BA_SPEC_PATH / BA_RULES_PATH / BA_EXCELDB_PATH / BA_SPECGEN_DIR，其中 SPECGEN_DIR 按“目录”语义）
  → 从 __file__ 向上 8 层、从 cwd 向上 4 层，找 repo 布局 <root>/work/ba/...
  → 同一批 root 下找裸文件名（扁平部署在这里命中：tools/official_spec.json、tools/ExcelDB.db、…）
  → 都没有 → 回落到原来的 ROOT 拼接（保持老行为，不抛异常）
```

未改动：任何字段/键序/数值/序列化逻辑、CLI 参数语义、`gen1017.py`、`specgen.py`、
`official_spec.json`、`initial_state_rules.json`、`ExcelDB.db`、`simple_payload.py`、`dto90004.py`。

---

## 3. 字节级一致性证明（仓库布局，改前 vs 改后）

方法：用**相同固定输入**跑两套代码 —— `account=10015354380`、
`now=2026-11-16T04:30:00`、`request_id=00000000-0000-4000-8000-000000000000`、
`mxtoken` 由账号派生；「改前」用的是把 4 个 `.orig` 放回
`<tmp>\ba_rep_before\work\ba\server\deploy\` 的**完整复刻仓库布局**（数据/抓包用硬链接）。

| 生成器 | 口径 | 改前 | 改后 | 判定 | sha256（改前 = 改后） |
|---|---|---|---:|---:|---|---|
| gen90004 | 紧凑包体 | 420 B | 420 B | 相同 | `17fa3c76951912e8959ff176ccaf5ab3f1e0472fb92afb3be82b9c7db897bc93` |
| gen90004 | pretty 落盘 | 488 B | 488 B | 相同 | `304e83224381b7fff196fd72ba2197e18ef20b4f798a4045bd895afd8b72d000` |
| gen90004 | `--compact` 落盘 | 421 B | 421 B | 相同 | `728d29a7954ce8759223f87bb8b20669da80fca194d189d4270cf7eaa9d236ee` |
| gen8000 | inner | 4,297 B | 4,297 B | 相同 | `d9dec8700968d5cdbdbb3ef3ba415dd5ca6859fca6adadc6bd2bd2eaf98c36b1` |
| gen8000 | ProgressDBs | 29 条 | 29 条 | 相同 | — |
| gen8000 | `write_output` 文件 | 10,889 B | 10,889 B | 相同 | `28f7155dadf12402391fec26115267e46daed90512accd47b35476d650c2cd47` |
| gen8000 | `--emit-catalog` | 144,429 B / 7,153 条 | 144,429 B / 7,153 条 | 相同 | `4b43b8314d2a0ac5a3ffa68f4e7d732ce7c2446788626d116232c96a1071c24c` |
| gen_simple 1005 | inner / wire | 267 / 556 B | 267 / 556 B | 相同 | `3cfc2be6ab599cf3501854b39c02d7767b07b132d78036645456e7b28d58e1ac` |
| gen_simple 4000 | inner / wire | 361 / 684 B | 361 / 684 B | 相同 | `c174ccc5c0ee444b84f51efa6c6635962b2c07ddf7ae62813f530e0a58a324fe` |
| gen_simple 26000 | inner / wire | 321 / 640 B | 321 / 640 B | 相同 | `a0be03780638248f9b5f70448367bd5845262fe917f424c0519fda61a5b0fba7` |

副 CLI 路径（rc / 全文对比，除临时输出目录名归一化外逐字符相同）：

| 命令 | rc | 结论行 |
|---|---:|---|
| `gen8000.py --selfcheck` | 0 | `selfcheck: PASS` |
| `gen8000.py --explain-variants` | 0 | 全量 1240 → 849 只给 39 → 10838 只给 35 |
| `gen90004.py --verify-official` | 0 | `官方逐字节复现 : PASS (9691 B 完全相同)` / spec_check PASS |
| `gen_simple.py --replay-official` | 0 | `结论: PASS（三个协议都能逐字节复现官方）` |

落盘文件逐字节比较：`t90004_compact.json` / `t90004_pretty.json` / `t8000.json` /
`emit_catalog.json` 四个文件 **IDENTICAL**。

证据文件：`evidence/snap_before2.json`、`evidence/snap_after2.json`（同目录）。

---

## 4. 扁平布局验证（假扁平目录）

构造：`C:\Users\su\AppData\Local\Temp\flat_test\`
- 平铺 13 个文件：`gen8000.py gen_simple.py gen90004.py gen_common.py gen1017.py
  simple_payload.py dto90004.py specgen.py spec_check.py official_spec.json
  initial_state_rules.json 8000_catalog.json` + `ExcelDB.db`
- `ExcelDB.db` 用 **NTFS 硬链接**（160,534,528 B，不复制）；`dto_extra/` 子目录只放 `proto90004_management.json`
- **不存在** `work/`、`report/` 任何层级；`cwd` 也不在仓库内

结果（`evidence/flat_snap.json`，22 项检查全 OK，`FLAT RESULT: PASS`）：

| 检查 | 结果 |
|---|---|
| 扁平目录无 `work/`、无 `report/` | OK |
| `SPEC_PATH / EXCELDB_PATH / DTO_EXTRA_DIR` 都命中 `flat_test\…` | OK |
| gen90004 inner 420 B，sha256 与仓库布局**相同**，pretty 落盘 488 B，spec_check FAIL=0 | OK |
| gen8000 inner 4,297 B / 29 条，sha256 **相同**，`P_SPECGEN/P_PROTO/P_EXCELDB` 全在扁平目录，内联 spec_check FAIL=0 | OK |
| gen_simple 1005 = 267/556、4000 = 361/684、26000 = 321/640，sha256 **相同** | OK |
| 三条 CLI（`gen90004 --compact --out`、`gen_simple --protocol 1005,4000,26000`、`gen8000 --out`）exit 0 | OK |
| `gen90004` 不给 `--out` 时默认路径在扁平目录可用（`flat_test\out\t90004.json`） | OK |

另跑第二次：`cwd=C:\`（与扁平目录无关）→ 同样 **22/22 OK**，证明不依赖 cwd。

**原版对照（问题复现）**：同一扁平目录放入 `.orig` 原文件后 ——
- `gen_common.SPEC_PATH -> C:\Users\su\work\ba\proto\official_spec.json`（不存在）
- `gen8000.build_response(...)` → `SystemExit: 找不到生成引擎: ...\work\ba\server\prototype\specgen.py`
- `gen90004.build(...)` → `FileNotFoundError: '...\work\ba\proto\official_spec.json'`
与任务描述的现象一致（线上同样是从 tools 往上 4 层 = `/`）。

**环境变量覆盖**（扁平目录内实测）：
`BA_SPEC_PATH` / `BA_RULES_PATH` / `BA_EXCELDB_PATH` 直接给出文件路径即生效；
`BA_SPECGEN_DIR` 按**目录**语义生效（与 `gen1017` 一致）；给不存在的路径时安全回落到扁平目录命中。

---

## 5. 服务器复验（`/www/wwwroot/bapatch/tools/`）

上传前后 sha256（线上与本地完全一致）：

| 文件 | 上传前（= 本地改前） | 上传后（= 本地改后） |
|---|---|---|
| `gen_common.py` | `847c5f26…e4fbf7` | `1998eb22…d577d92` |
| `gen8000.py` | `3159d3d5…c7e3fb` | `9432e4ee…c867598` |
| `gen_simple.py` | `57e3a524…46f286` | `93461a08…b3d8a1` |
| `gen90004.py` | `c1ca45ca…2dc236` | `67128f8d…ba1492` |

`cd /www/wwwroot/bapatch/tools && python3 -B /tmp/ba_flatpath_verify.py`，实际输出（Python 3.10.12）：

```
PROTO_DIR      /www/wwwroot/bapatch/tools  exists=True
SPEC_PATH      /www/wwwroot/bapatch/tools/official_spec.json  exists=True
DTO_EXTRA_DIR  /www/wwwroot/bapatch/tools/dto_extra  exists=True
EXCELDB_PATH   /www/wwwroot/bapatch/tools/ExcelDB.db  exists=True
DECODED_DIR    /report/_tmp/official_decoded_201  exists=False      ← 线上本来就没有抓包

[90004]   inner bytes 420 OK / inner sha256 17fa3c76… OK / pretty 落盘 488 OK / spec_check FAIL 0 OK
[8000]    inner bytes 4297 OK / inner sha256 d9dec870… OK / ProgressDBs 29 OK / spec_check FAIL 0 OK
[1005]    267 / 556 OK（sha 3cfc2be6…）      [4000] 361 / 684 OK（sha c174ccc5…）
[26000]   321 / 640 OK（sha a0be0378…）
RESULT: PASS 全部字节数与本地一致
```

附带：`gen1017.build()` 在线上仍为 `top_keys=35 / inner=83804 B`（与改造前记录一致，说明未受波及）。

---

## 6. 线上文件未被触碰的证明

```
$ cd /www/wwwroot/bapatch/tools
$ sha256sum account_auth_probe.py
b9e248879051681fc2daa9e375d3023dafd17afb14098c9ccc0f53c2da9a6f0d   ← 与要求一致
$ ps -ef | grep account_auth_probe | grep -v grep
root     2532984       1  0 06:30 ?  00:00:00 python3 account_auth_probe.py   ← pid 未变、启动时间 06:30
$ ls cn_1017_mode.txt cn_preempt.txt
ls: cannot access 'cn_1017_mode.txt': No such file or directory
ls: cannot access 'cn_preempt.txt': No such file or directory
```

其它旁证：
- `account_auth_probe.py`：76,098 B，mtime `2026-11-16 06:30:06`（早于本次操作 06:41）；
- `tools/` 下 mtime 晚于 06:35 的文件**只有 4 个**：`gen_common.py / gen8000.py / gen_simple.py / gen90004.py`；
- `gen1017.py / specgen.py / spec_check.py / official_spec.json / initial_state_rules.json /
  simple_payload.py / dto90004.py / ExcelDB.db` 的 sha256 线上与本地**逐一相同**（未动）；
- `/www/wwwroot/bapatch/cn_bridge_exp.txt` 仍是 Nov 14 04:13；`/www/wwwroot/bapatch/ba_srv/` mtime 06:18（早于本次操作）；nginx `active`（未重启）；
- 没有 apply 任何 `patch_*.py`，没有重启任何服务，没有删除任何 `.bak`/旧文件；
  备份是新增的 `*.pre_flatpath.20261116_064112`。

---

## 7. 结论

- 三个生成器（`gen8000 / gen_simple / gen90004`，依赖 `gen_common`）**现在能在扁平目录
  `/www/wwwroot/bapatch/tools/` 下正常 import 并 build**，且输出与仓库布局下**逐字节相同**
  （420 / 4297 / 267·556 / 361·684 / 321·640，sha256 全部一致）。
- 仓库布局不受影响：所有数据路径解析结果与改造前完全一致，`--emit-catalog`、`--selfcheck`、
  `--explain-variants`、`--verify-official`、`--replay-official` 全部 rc=0 且输出一致。
- 局限（改造前也一样，与本次改动无关）：线上没有 `report/_tmp/official_decoded_201`，
  因此**依赖官方抓包的自证模式**在线上不可用 —— `gen8000 --selfcheck` 会在 ③ 返回 3、
  `--explain-variants` 会因缺抓包报错、`gen_simple --replay-official` 三条 SKIP、
  `gen90004 --official/--verify-official` 不可用。**build 完全不需要抓包**。
- `gen_common.ROOT` 保持「仓库根」语义未动（供输出目录用）；`gen24000/gen36001` 等
  未在本次范围内的生成器在线上仍按老路径，需要时按同一模式再改。
