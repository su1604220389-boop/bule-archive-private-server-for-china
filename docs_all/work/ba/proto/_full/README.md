# `_full/` —— 全量 Response DTO 提取流水线（国服 BA，444 具名 DTO）

所有输入只读，产物全部是本目录/上级目录的新文件。禁止联网/ssh/adb。

## 产物

| 文件 | 说明 |
|---|---|
| `../dto_schema_full.json` | **最终 schema**：444 个响应 DTO + 13 个额外恢复映射 + 250 个 support 类型 + 2 个基类 |
| `../gen_full.py` | **统一响应生成器**（`--list/--protocol/--dto/--check/--missing`） |
| `../protocol_extras.json` | `protocol_map.json` 里 `resp=null` 但名字严格对上的 13 条协议映射 |
| `worklist.json` | 444 个 resp DTO 按段清单（缺口/已覆盖） |
| `generic_map.json` | 全部 unresolved typeIndex 的裁定表（type/kind/conf/src/uses/votes） |
| `support_types.json` | 可达 support 类型（含 List/Dict 元素，`--inner`） |
| `draft/seg_*.json` | 引擎按段草稿（子 agent 的起点） |
| `seg_*.json` | 子 agent 校对后的分段产物（合并输入） |
| `report_stats.json` / `report_facts.json` | 报告 §1/§2/§3 的数字来源 |

## 流水线

```powershell
cd C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\proto

python _full\worklist.py                          # 1. 工作清单
python _full\extract_core.py --stats              # 2. 看解析率
python _full\extract_core.py --dump-all           #    -> _full/draft/seg_*.json
python _full\extract_core.py --generic-map        #    -> _full/generic_map.json
python _full\extract_core.py --support --inner    #    -> _full/support_types.json

python _full\make_seg.py --segs 21,22 --out _full\seg_21-29.json   # 3. 分段工作文件
python _full\verify_seg.py --segs 21,22 --file _full\seg_21-29.json # 4. 分段验收

python _full\make_extras.py                       # 5. 额外协议映射
python _full\merge_full.py                        # 6. 合并 -> dto_schema_full.json
python gen_full.py --check --quiet                  # 7. 必须 exit 0

python _full\stats_for_report.py
python _full\report_facts.py
python _full\make_report.py                       # -> report/72-全量DTO提取总表.md
python _full\verify_raw_metadata.py               # 独立证据：从原始 metadata 重建并逐字节比对
```

## 核心规则（元数据口径）

1. 解混淆：`global-metadata.dat` 头 `0x120` 字节 XOR `0x66`；每 64KB 页的 `[0x1000,0x5000)` XOR `0x66`。重建结果与 `report/_tmp/patch/md_deob.bin` **逐字节相同**（sha256 `245d6e3b…`），`verify_raw_metadata.py` 会复核。
2. 表位置（来自解混淆后的头）：`methods@0x8B2C14`(36B)、`typeDefinitions@0x1F02148`(88B)、`fields@0x1B17590`(12B)、`string@0xEC9C8`。
3. 字段类型：`field.typeIndex - 1 == typeDefinition.byvalTypeIndex` ⇒ 该 typedef（`conf=high`）。
4. 泛型实例（`List<>/Dictionary<>/Nullable<>`）不在 typedef 表 ⇒ 全程序 `(类.字段)→typeIndex` 投票；无票时按使用处命名/抓包推断（`src` 写明依据）。
5. 继承：`typeDefinition.q[4]` 是父类型 typeIndex（`q[4]-1` 命中父 typedef 的 byval）。444 个响应里只有 3 条特殊链（AccountAuth2 / ShopBuyGacha3 / ShopPickupSelectionGachaBuy）；support 类型的父类字段已展开进 `fields`。
6. 真·空响应：`fieldCount=0` 且 `fieldStart=0xFFFFFFFF`，且 methods 只有 `get_Protocol`+`.ctor`（44 个）。
7. static/const 字段（`Zero/One/Epsilon/MaxValue/...`）在 metadata 里与实例字段无法区分，按名字剔除，记在条目的 `staticSkipped`。
8. `T?`（可空引用注解）= `T`；只有 `Nullable<T>` 才是 null。

## 已知不确定项

- support 类型里仍有 `unknown` 字段（`report_facts.json` 的 `supportUnknown`），均为无 byval、无投票、无抓包的泛型实例；生成时按字段名兜底（复数→`[]`，Dict→`{}`，其余→`null`）。
- `ResponsePacket.StaticOpenConditions` 用抓包形态（dict 55 键全 0），不是旧 schema 的 `List<OpenConditionDB>`。
- `BasisPoint` 线上只有 `rawValue`（fixpoint ×10000）。
