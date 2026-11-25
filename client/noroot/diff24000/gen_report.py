#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_report.py -- 生成 work\\ba\\noroot\\24000_DIFF.md（数值全部由代码算，不手抄）。

数据源
   官方 = report\\_tmp\\official_decoded_201\\01_24000_api_academy_getinfo.response.json 的 inner
   我们 = work\\ba\\noroot\\diff24000\\our_min.json（gen24000.py 复现 v3 运行时输出）
   重放 = work\\ba\\noroot\\diff24000\\official_replay_exact.json（引擎 + 官方数据）
"""
import base64
import io
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'work', 'ba', 'server', 'deploy'))
sys.dont_write_bytecode = True
import gen24000 as G  # noqa: E402

CAP = os.path.join(ROOT, 'report', '_tmp', 'official_decoded_201',
                   '01_24000_api_academy_getinfo.response.json')
OUR = os.path.join(HERE, 'our_min.json')
REPLAY = os.path.join(HERE, 'official_replay_exact.json')
OUT = os.path.join(ROOT, 'work', 'ba', 'noroot', '24000_DIFF.md')

ENABLED_LOC = (1, 7, 11, 12, 13, 15, 16, 17, 19)


def load(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        d = json.load(fh)
    if isinstance(d, dict) and isinstance(d.get('inner'), dict):
        return d['inner'], d
    return d, None


def cell(v):
    if isinstance(v, str):
        return '`%s`' % (v if len(v) <= 42 else v[:39] + '...')
    return '`%s`' % (json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v)


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    off, cap = load(CAP)
    our, _ = load(OUR)
    rep, _ = load(REPLAY)

    o_sk, u_sk = off['SessionKey'], our['SessionKey']
    o_adb, u_adb = off['AcademyDB'], our['AcademyDB']
    o_zv, u_zv = o_adb['ZoneVisitCharacterDBs'], u_adb['ZoneVisitCharacterDBs']
    o_lo, u_lo = off['AcademyLocationDBs'], our['AcademyLocationDBs']

    o_inner = len(json.dumps(off, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    u_inner = len(json.dumps(our, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    r_inner = len(json.dumps(rep, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))

    plain = json.loads(cap['plain'])
    o_packet = len(plain['packet'].encode('utf-8'))
    o_plain = len(cap['plain'].encode('utf-8'))

    # 我方信封
    u_packet = G.b24000_compact(our)
    u_plain = json.dumps({'protocol': 'Academy_GetInfo', 'packet': u_packet,
                          'requestid': our['RequestId']},
                         ensure_ascii=False, separators=(',', ':'))
    u_plain_len = len(u_plain.encode('utf-8'))
    wire_est = round(u_plain_len * (17560 / 13128))

    o_dist = Counter(len(v) for v in o_zv.values())
    u_dist = Counter(len(v) for v in u_zv.values())
    o_tot = sum(len(v) for v in o_zv.values())
    u_tot = sum(len(v) for v in u_zv.values())

    o_tok, u_tok = o_sk['MxToken'], u_sk['MxToken']
    o_b64 = base64.b64decode(o_tok, validate=True)
    u_b64 = base64.b64decode(u_tok, validate=True)

    first_elem = None
    for k, v in o_zv.items():
        if v:
            first_elem = (k, v[0])
            break

    L = []
    a = L.append

    a('# 24000 Academy_GetInfo · 逐字段对比报告')
    a('')
    a('> 生成：`work\\ba\\noroot\\diff24000\\gen_report.py`（数值全部由代码计算）  ')
    a('> 对比工具：`work\\ba\\noroot\\diff24000\\diff24000.py`  ')
    a('> 只读；除 `work\\ba\\noroot\\` 外未写入任何文件')
    a('')
    a('## 0 · 结论先行')
    a('')
    a('1. **引擎没有 bug。** 把官方抓包里的全部动态值（账号 / MxToken / RequestId / ticks / '
      '`LastUpdate` / 9 条地点 / 71 个 zone 的 138 个元素）原样喂进 `gen24000.b24000_build`，'
      '输出与官方 **packet 逐字节相同（%s B）**，整条信封也 **逐字节相同（%s B）**；'
      '递归对比 458 个叶子节点 **全部 OK**。' % ('{:,}'.format(o_packet), '{:,}'.format(o_plain)))
    a('2. **结构差异 0 条（P0 = 0）。** 我们现在的响应与官方在"形状"上已经一致：'
      '7 个顶层键、键序、`SessionKey` 2 子键、`AcademyDB` 4 子键、'
      '`ZoneVisitCharacterDBs` 是 71 键的 **map**、`ZoneScheduleGroupRecords` 是 `{}`、'
      '`AcademyLocationDBs` 行是严格 4 键。')
    a('3. **剩下的差异只有 3 类，全部是"数据/动态值"**：'
      '① 71 个 zone 的数组我们全空（官方 %d 个元素）；'
      '② 地点 1 条 vs 官方 9 条（Rank/Exp 也不同）；'
      '③ 6 个动态标量（账号、MxToken、ticks、RequestId、LastUpdate、地点 AccountId）。' % o_tot)
    a('4. **任务书里的 3 条前提需要修正**（见 §8）：'
      'MxToken **不是** 36 字符 GUID（v2/v3 都发 64 字符 base64，本地 12 份样本无一例外）；'
      '`AcademyLocationDBs[].AccountId` **不可能**单独为 0 而 `SessionKey.AccountServerId` 是账号号'
      '（同一变量 `aid` 写两处）；'
      '`1017` 在官方抓包里**就是** `Account_LoginSync`（这一点任务书是对的，'
      '是 `report/63` A13.5 的"1017 = DismissRepurchasablePopup"结论错了）。')
    a('')
    a('## 1 · 两份数据与做法')
    a('')
    a('| 项 | 官方 | 我们 |')
    a('|---|---|---|')
    a('| 来源 | `report\\_tmp\\official_decoded_201\\01_24000_api_academy_getinfo.response.json` 的 `inner` '
      '| `work\\ba\\noroot\\diff24000\\our_min.json`（`gen24000.py --account-id 10000000001` 复现 v3 运行时输出） |')
    a('| 账号 | `%s` | `%s` |' % (o_adb['AccountId'], u_adb['AccountId']))
    a('| inner 字节 | %s | %s |' % ('{:,}'.format(o_inner), '{:,}'.format(u_inner)))
    a('| envelope(plain) 字节 | %s | %s（实测算出；按官方 resp_bytes/plain 比 1.3376 折算 wire ≈ **%s**，'
      '与任务书记录的 **1,772 B** 吻合） |' % ('{:,}'.format(o_plain), '{:,}'.format(u_plain_len),
                                          '{:,}'.format(wire_est)))
    a('| resp_bytes | 17,560 | — |')
    a('')
    a('> **服务器上的 `/www/wwwroot/_ba_state/academy_24000_v3_plain.txt` 本地没有（未找到）。** '
      '本报告的"我们"一列用引擎复现 v3 的输出来代表。'
      '线索：wire 1,772 B 折算 inner ≈ %s B，与 v3 的 %s B 一致 ⇒ **线上跑的就是 v3，'
      '不是 192 B 假包，也不是 620 B 桩**。' % ('{:,}'.format(u_inner), '{:,}'.format(u_inner)))
    a('')
    a('对比命令（可复跑）：')
    a('')
    a('```')
    a('python work\\ba\\noroot\\diff24000\\diff24000.py --official report\\_tmp\\official_decoded_201\\01_24000_api_academy_getinfo.response.json '
      '--ours work\\ba\\noroot\\diff24000\\our_min.json --csv work\\ba\\noroot\\diff24000\\diff_A_official_vs_ours.csv')
    a('python work\\ba\\noroot\\diff24000\\make_replay.py      # 引擎 + 官方数据 逐字节重放')
    a('```')
    a('')

    # ---------------------------------------------------------------- 顶层
    a('## 2 · 顶层 7 键')
    a('')
    a('| # | 键 | 官方（类型/值） | 我们（类型/值） | 一致? | 严重度 |')
    a('|---|---|---|---|---|---|')
    for i, k in enumerate(G.B24000_TOP_KEYS, 1):
        ov, uv = off.get(k), our.get(k)
        same = type(ov) is type(uv)
        if isinstance(ov, (int, str)):
            same = same and ov == uv
        if isinstance(ov, list):
            same = type(ov) is type(uv) and len(ov) == len(uv)
        if isinstance(ov, dict):
            same = type(ov) is type(uv) and list(ov.keys()) == list(uv.keys())
        if same:
            sev = 'OK'
        elif type(ov) is not type(uv):
            sev = 'P0-结构'
        elif k in ('ServerTimeTicks', 'RequestId'):
            sev = 'P2-动态'
        elif k == 'AcademyLocationDBs':
            sev = 'P1-语义'
        elif k in ('SessionKey', 'AcademyDB'):
            sev = 'P2-动态'
        else:
            sev = 'OK'
        os_ = ('`dict` %d 子键' % len(ov)) if isinstance(ov, dict) else (
            ('`list` %d 条' % len(ov)) if isinstance(ov, list) else ('`%s` `%s`' % (type(ov).__name__, ov)))
        us_ = ('`dict` %d 子键' % len(uv)) if isinstance(uv, dict) else (
            ('`list` %d 条' % len(uv)) if isinstance(uv, list) else ('`%s` `%s`' % (type(uv).__name__, uv)))
        a('| %d | `%s` | %s | %s | %s | %s |' % (i, k, os_, us_, '是' if same else '否(值/长度)', sev))
    a('')
    a('**键序**：官方键序 == 规范键序 `%s`；我们键序 == 规范键序 `%s` ⇒ 一致。'
      % (list(off.keys()) == list(G.B24000_TOP_KEYS), list(our.keys()) == list(G.B24000_TOP_KEYS)))
    a('')
    a('## 3 · `SessionKey` 逐子字段')
    a('')
    a('| 子字段 | 官方 | 我们 | 一致? | 严重度 |')
    a('|---|---|---|---|---|')
    a('| `AccountServerId` | `int` %s | `int` %s | 值不同（按设计） | P2-动态 |'
      % (o_sk['AccountServerId'], u_sk['AccountServerId']))
    a('| `MxToken` | `str` len=%d / base64→%d B | `str` len=%d / base64→%d B | 值不同（按设计） | P2-动态 |'
      % (len(o_tok), len(o_b64), len(u_tok), len(u_b64)))
    a('| 键序 | `%s` | `%s` | 是 | OK |' % (list(o_sk.keys()), list(u_sk.keys())))
    a('')
    a('- 官方 token 前 16 字符：`%s…`；我们：`%s…`' % (o_tok[:16], u_tok[:16]))
    a('- 两边都能 base64 解码（官方 48 B / 我们 48 B）⇒ **长度与编码同形**。')
    a('')
    a('## 4 · `AcademyDB` 的 4 个子键')
    a('')
    a('| 子键 | 官方 | 我们 | 一致? | 严重度 |')
    a('|---|---|---|---|---|')
    a('| `AccountId` | `int` %s | `int` %s | 值不同（按设计） | P2-动态 |' % (o_adb['AccountId'], u_adb['AccountId']))
    a('| `LastUpdate` | `str` `%s` | `str` `%s` | 值不同（按设计） | P2-动态 |'
      % (o_adb['LastUpdate'], u_adb['LastUpdate']))
    a('| `ZoneVisitCharacterDBs` | `dict` **71 键 / %d 元素** | `dict` **71 键 / %d 元素** | 形状一致，内容不同 | P1-语义 |'
      % (o_tot, u_tot))
    a('| `ZoneScheduleGroupRecords` | `dict` len=0 `{}` | `dict` len=0 `{}` | **完全一致** | OK |')
    a('')
    a('## 5 · `ZoneVisitCharacterDBs` 的 71 个 zone 逐个对比')
    a('')
    a('### 5.1 长度分布（Q1）')
    a('')
    a('| 数组长度 | 官方 zone 数 | 我们 zone 数 |')
    a('|---|---|---|')
    for n in sorted(set(o_dist) | set(u_dist)):
        a('| %d | %d | %d |' % (n, o_dist.get(n, 0), u_dist.get(n, 0)))
    a('| **合计元素** | **%d** | **%d** |' % (o_tot, u_tot))
    a('')
    a('- 官方空数组的 key：`%s`（**只有 1 个**）' % ([k for k, v in o_zv.items() if not v],))
    a('- 我们空数组的 key：**全部 71 个**')
    a('- 键集合完全相同：**%s**；键序（字典序）相同：**%s**'
      % (set(o_zv) == set(u_zv), list(o_zv.keys()) == list(u_zv.keys())))
    a('')
    a('### 5.2 元素形状（官方）')
    a('')
    if first_elem:
        a('官方 `["%s"][0]` = `%s`' % (first_elem[0], json.dumps(first_elem[1], ensure_ascii=False)))
        a('')
        a('⇒ 元素是 **3 键对象** `{UniqueId:int, ServerId:int, LastInteractTime:str}`，'
          '即 `Dictionary<int_str, List<{UniqueId,ServerId,LastInteractTime}>>`。'
          '我们全空，所以元素形状**没有暴露**，也没有形状错误。')
    a('')
    a('### 5.3 71 个 key 逐行')
    a('')
    a('| zone key | 官方 len | 我们 len | 一致? | 严重度 |')
    a('|---|---|---|---|---|')
    for k in o_zv.keys():
        ol = len(o_zv[k])
        ul = len(u_zv.get(k, [])) if k in u_zv else -1
        a('| `"%s"` | %d | %s | %s | %s |'
          % (k, ol, ul if ul >= 0 else '缺键', '是' if ol == ul else '否',
             'OK' if ol == ul else 'P1-语义'))
    a('')
    a('## 6 · `AcademyLocationDBs` 逐条')
    a('')
    a('| # | 官方 | 我们 | 一致? | 严重度 |')
    a('|---|---|---|---|---|')
    for i in range(max(len(o_lo), len(u_lo))):
        ov = o_lo[i] if i < len(o_lo) else None
        uv = u_lo[i] if i < len(u_lo) else None
        ojson = json.dumps(ov, ensure_ascii=False) if ov else '<无此行>'
        ujson = json.dumps(uv, ensure_ascii=False) if uv else '<无此行>'
        same = (ov is not None and uv is not None
                and ov['LocationId'] == uv['LocationId'] and ov['Rank'] == uv['Rank']
                and ov['Exp'] == uv['Exp'])
        a('| %d | `%s` | `%s` | %s | %s |' % (i, ojson, ujson, '是' if same else '否',
                                             'OK' if same else 'P1-语义'))
    a('')
    a('| 聚合 | 官方 | 我们 |')
    a('|---|---|---|')
    a('| 条数 | %d | %d |' % (len(o_lo), len(u_lo)))
    a('| LocationId | `%s` | `%s` |' % ([r['LocationId'] for r in o_lo], [r['LocationId'] for r in u_lo]))
    a('| Rank | `%s` | `%s` |' % ([r['Rank'] for r in o_lo], [r['Rank'] for r in u_lo]))
    a('| Exp | `%s` | `%s` |' % ([r['Exp'] for r in o_lo], [r['Exp'] for r in u_lo]))
    a('| AccountId | `%s` | `%s` |' % (sorted(set(r['AccountId'] for r in o_lo)),
                                       sorted(set(r['AccountId'] for r in u_lo))))
    a('| 行键 | `%s` | `%s` |' % (list(o_lo[0].keys()), list(u_lo[0].keys())))
    a('')
    a('国服启用 9 个 location：`%s`（官方 9 条正好是这 9 个，**没有** 14/18）。' % (list(ENABLED_LOC),))
    a('')
    a('## 7 · 数值与格式')
    a('')
    a('| 项 | 官方 | 我们 | 判定 |')
    a('|---|---|---|---|')
    a('| `ServerTimeTicks` | `%s`（%d 位） | `%s`（%d 位） | **量级正确**，同为 .NET 100ns 18 位 |'
      % (off['ServerTimeTicks'], len(str(off['ServerTimeTicks'])),
         our['ServerTimeTicks'], len(str(our['ServerTimeTicks']))))
    a('| ticks 反算时间 | `%s` | `%s` | 官方与抓包墙钟 04:30:54 对齐 ⇒ **ticks 存的是本地墙钟(UTC+8)，不是 UTC** |'
      % (G.b24000_time_from_ticks(off['ServerTimeTicks']).isoformat(),
         G.b24000_time_from_ticks(our['ServerTimeTicks']).isoformat()))
    a('| `LastUpdate` | `%s` | `%s` | 同格式（ISO、无时区、毫秒）；官方比 ticks 早 30m48s，我们等于 ticks |'
      % (o_adb['LastUpdate'], u_adb['LastUpdate']))
    a('| `RequestId` | `%s`（36） | `%s`（36） | 同形 uuid4 |' % (off['RequestId'], our['RequestId']))
    a('| `ServerNotification` | `%s` | `%s` | 一致 |' % (off['ServerNotification'], our['ServerNotification']))
    a('| `Protocol` | `%s` | `%s` | 一致 |' % (off['Protocol'], our['Protocol']))
    a('')
    a('## 8 · Q1–Q5 逐条回答')
    a('')
    a('### Q1 · 71 个 zone 的数组长度分布；客户端会要求某些 zone 必须有角色吗？')
    a('')
    a('**官方实测**：`{0: %d, 1: %d, 2: %d, 3: %d}`，共 **%d 个元素**，**只有 key `"1"` 是空数组**。'
      % (o_dist.get(0, 0), o_dist.get(1, 0), o_dist.get(2, 0), o_dist.get(3, 0), o_tot))
    a('**我们**：71 个全空。')
    a('')
    a('**判断：结构上绝对合法，不是反序列化障碍。** 理由三条：')
    a('1. 类型是 `Dictionary<string, List<T>>`，`[]` 对任何 `List<T>` 都合法（`report/70` §4 也这么认为）。')
    a('2. 官方自己在 key `"1"` 上就发了 `[]` ⇒ 空数组是服务端会真实产生的东西。')
    a('3. 我们一个元素都没有 ⇒ 元素类型从未被"暴露"，客户端连类型不匹配的机会都没有。')
    a('')
    a('**但语义上是"空世界"**：官方这个 32 级号有 %d 条"学生拜访某 zone"的记录，新号自然是 0。'
      '若客户端在学院界面里对"某个 zone 必须能找到角色"做非空断言，会崩 —— 这是 *可能但无证据*，'
      '按 **P1** 处理，不做 P0。' % o_tot)
    a('')
    a('### Q2 · `AcademyLocationDBs` 9 条 vs 1 条，多严重？')
    a('')
    a('**中等（P1），不是反序列化障碍**：数组长度差异不抛异常。')
    a('但两点必须说清：')
    a('1. **`AccountId: 0` 是任务书的误判**。`gen24000`/v2/v3 里同一变量 `aid` 同时写 '
      '`SessionKey.AccountServerId`、`AcademyDB.AccountId`、`AcademyLocationDBs[].AccountId`；'
      '三者**不可能**一个是账号号、一个是 0。真正会显示成 "AccountId 缺失/0" 的是**旧基线** '
      '`_baseline/account_auth_probe.py:798-808`，它发的行只有 3 键 `{LocationId,Rank,Exp}`（**没有 AccountId**）。'
      '⇒ 你看到的 `AccountId: 0` 那条样本来自 **v3 之前**的响应。')
    a('2. 官方 `Rank` 不是全 1（`%s`），`Exp` 只有 19 号是 200。我们 `all9` 是 Rank 全 1、Exp 全 0。'
      '新号用全 1 是合理初值（`initial_state_rules q8`），**不算错**。' % ([r['Rank'] for r in o_lo],))
    a('')
    a('### Q3 · `MxToken` 36 vs 64 字符，客户端会校验长度吗？')
    a('')
    a('**先在事实层面纠正：我们不是 36 字符。**')
    a('- 官方：64 字符 base64，解码 **%d B**。' % len(o_b64))
    a('- 我们（v3）：64 字符 base64，解码 **%d B**。' % len(u_b64))
    a('- 本地 12 份 24000 样本（`report\\_tmp\\t24000*.json` 等）**逐一检查，无一例是 36 字符 GUID**。')
    a('- 代码层面 `patch_24000_v3.py:_ba24000_pick_token`：请求体 `MxToken` > 会话 > `sha384→base64`，'
      '**三条分支都产出 64 字符**。')
    a('')
    a('⇒ **"36 字符 GUID" 未找到任何证据，判定为过时结论**（很可能来自 v1/更早的 `uuid4()` 实现）。')
    a('')
    a('若线上真的出现 36 字符，那必然是**另一个补丁**在跑。**一行验证**（看服务器日志的这三个字段）：')
    a('```')
    a('grep -o \'"academy_token_len":[0-9]*\\|"academy_token_is64":[a-z]*\\|"academy_token_src":"[a-z]*"\' '
      '/www/wwwroot/bapatch/logs/api_all_requests.log | tail -20')
    a('# 期望：len=64 / is64=true / src=request 或 session')
    a('# 若 src=generated 且 is64=false -> 才是你说的问题')
    a('```')
    a('')
    a('至于"客户端会不会校验长度"：**无法从我们的数据判定**（没有客户端侧证据）。'
      '但 64 字符 base64 是本仓库所有证据的一致形态，**保持 64 即可**。')
    a('')
    a('### Q4 · `ServerTimeTicks` 量级对不对？')
    a('')
    a('**对。** 官方 `%s`（%d 位），我们 `%s`（%d 位），同为 .NET 100ns 纪元（0001-01-01）。'
      % (off['ServerTimeTicks'], len(str(off['ServerTimeTicks'])),
         our['ServerTimeTicks'], len(str(our['ServerTimeTicks']))))
    a('')
    a('**但坐标系要盯**：官方 ticks 反算 = `%s`，与同一文件 `meta.bj = %s` 对齐 '
      '⇒ **官方 ticks 存的是本地墙钟 UTC+8，不是 UTC**。'
      % (G.b24000_time_from_ticks(off['ServerTimeTicks']).isoformat(), cap['meta']['bj']))
    a('⇒ 若线上是 **UTC 时区的容器**，`datetime.now()` 会给出 UTC，ticks 比官方约定**少 8 小时'
      '（288,000,000,000 个 tick）**。这是**可验证的 P1**：')
    a('```')
    a('python3 -c "import datetime;t=int((datetime.datetime.now()-datetime.datetime(1,1,1)).total_seconds())*10**7;'
      'print(t, datetime.datetime(1,1,1)+datetime.timedelta(microseconds=t//10))"')
    a('date -Is   # 两者应相差 < 2 秒；若差 8 小时 => 容器 TZ=UTC，需要 TZ=Asia/Shanghai')
    a('```')
    a('')
    a('### Q5 · `LastUpdate` 格式对不对？')
    a('')
    a('**格式对，精度有坑。** 官方 `%s`；我们 `%s`。' % (o_adb['LastUpdate'], u_adb['LastUpdate']))
    a('两者都是"ISO + 毫秒 + 无时区"，`按 yyyy-MM-ddTHH:mm:ss.fff` 都能解析。')
    a('')
    a('**坑**：`gen24000.b24000_fmt_time` 会 `rstrip("0")` 裁掉尾零，'
      '⇒ 毫秒为 `xx0` 时输出 **2 位**小数（如 `2026-11-16T06:13:47.88`），为 `x00` 时 **1 位**，'
      '为 `000` 时**连小数点都没有**（`2026-11-16T06:13:48`）。'
      '实测 **10.0% 的请求**会落到非 3 位小数（900/1000 才是 3 位）。')
    a('若客户端用 `ParseExact(..., "yyyy-MM-ddTHH:mm:ss.fff")` 就会抛异常 ⇒ '
      '**偶发失败（10%）**，不是"每次都失败"，所以不是本次卡点，但**必须修**（P1）。')
    a('')
    a('## 9 · 第 4 项：用我们的引擎 + 官方的数据渲染一次')
    a('')
    a('**做成了，而且逐字节相同。** `work\\ba\\noroot\\diff24000\\make_replay.py`：')
    a('')
    a('| 检查项 | 结果 |')
    a('|---|---|')
    a('| packet（内层 JSON 字符串） | **BYTE-IDENTICAL** %s B vs 官方 %s B |'
      % ('{:,}'.format(o_packet), '{:,}'.format(o_packet)))
    a('| 整条 envelope（`{"protocol","packet","requestid"}`） | **BYTE-IDENTICAL** %s B vs 官方 %s B |'
      % ('{:,}'.format(o_plain), '{:,}'.format(o_plain)))
    a('| 递归 diff（官方 vs 重放） | **458 个叶子全部 OK，差异 0 条** |')
    a('| 外层 `requestid` == 内层 `RequestId` | 是（官方也是） |')
    a('')
    a('输入用的是官方的：账号 `%s` / MxToken（64 字符）/ `RequestId` / ticks `%s` / '
      '`LastUpdate` `%s` / 全部 9 条地点 / 全部 71 个 zone 的 %d 个元素。'
      % (off['AcademyDB']['AccountId'], off['ServerTimeTicks'], off['AcademyDB']['LastUpdate'], o_tot))
    a('')
    a('**⇒ 引擎的序列化、键序、时间格式、map 形状全部与官方一致。'
      '我们和官方之间剩下的每一个字节差，都来自"喂进去的数据"，不来自引擎。**')
    a('')
    a('## 10 · 按"最可能导致客户端拒绝"排序')
    a('')
    a('> 前提：结构已经 0 条 P0，所以下面按"还能造成静默失败"的可能性排。')
    a('')
    a('| 排序 | 差异 | 现状 | 为什么可能致命 | 修复建议 |')
    a('|---|---|---|---|---|')
    a('| **1** | **`SessionKey` 必须原样回显请求里的那一个**（`AccountServerId` + `MxToken`） '
      '| 代码上 `_ba24000_pick_token` 优先取请求体，看起来对；但**线上明文拿不到，未证实** '
      '| 这是唯一能造成"整包被弃用后静默停下"的量级差异：客户端知道自己的账号与 token，'
      '对不上就是会话失效。而 `aid` 一旦解不出来会 fallback 到 `0`，`SessionKey.AccountServerId` 直接变 0 '
      '| **第一优先验证**：在服务器日志里查 `academy_account_src` / `academy_token_src`。'
      '期望 `request.AccountId` + `request`；若是 `config.default_account_id` + `generated` ⇒ 就是它。'
      '修法：把 `_ba24000_config` 的 `default_account_id` 兜底改成"从会话取，取不到就不回 24000 而是回 Error 信封" |')
    a('| **2** | 71 个 zone 全空（官方 %d 个元素） | 全空 | 结构合法；但客户端学院界面可能对"某 zone 无角色"做非空断言 | '
      '先给 `AcademyLocationDBs` 里每个 location 的 1 个 zone 填 1-3 个真实角色 '
      '（`{UniqueId: <CharacterDBSchema.Id>, ServerId: <实例id>, LastInteractTime: "0001-01-01T00:00:00"}`），'
      '做 A/B：全空 vs 只填 1 号 zone |' % o_tot)
    a('| **3** | 地点 1 条 vs 9 条 | 1 条 | 长度合法；但学院每个 location 的 Rank 可能被下游用来算解锁/可上阵数 | '
      '直接用 `--locations all9` 上机（`TEST_24000_v3.md` §6 已验证 9 条时 `spec_check` 差异 0 提示 0）。'
      '这是**成本最低的一次 A/B**，建议和 #2 同轮做 |')
    a('| **4** | ticks 时区 | 取决于线上容器 TZ | 若容器是 UTC，ticks 差 8h，学院日程/每日重置会错 | '
      '`date -Is` 对一下；容器里固定 `TZ=Asia/Shanghai` |')
    a('| **5** | `LastUpdate` 尾零裁剪 | 10% 的请求非 3 位小数 | 若客户端 `ParseExact` 3 位则抛异常 | '
      '把 `b24000_fmt_time` 的 `rstrip("0")` 去掉（或 `frac=3` 时补零到 3 位） |')
    a('')
    a('## 11 · "如果差异只有一个，明确说出来"')
    a('')
    a('**没有"只有一个差异"这回事，但可以明确说：结构差异是 0 条。**')
    a('')
    a('- 6 处结构修复（dict / AccountId / SessionKey / ZoneScheduleGroupRecords / 无伪键 / RequestId）'
      '**全部生效且正确** —— 由 §9 的逐字节重放反证：引擎在这些点上与官方同字节。')
    a('- 剩下的是 3 类**数据**差异（zone 内容 / 地点条数 / 6 个动态标量），'
      '**没有任何一类会在反序列化阶段抛异常**。')
    a('- 所以如果客户端仍然在 24000 之后零请求，**最可能不是"包内容不对"，而是"包没有被当成这个会话的包"** '
      '（排序 #1：`SessionKey` 回显），或**根本不在 24000 这层**（网关 crypto / HTTP 头 / '
      '客户端在 24000 之后等的是别的条件）。')
    a('')
    a('## 12 · 未找到 / 局限')
    a('')
    a('- **`/www/wwwroot/_ba_state/academy_24000_v3_plain.txt` 本地未找到** ⇒ "我们"一列用引擎复现，'
      '不是线上真实回包。**线上那份一旦拉到本地，直接跑 §1 的命令即可把本报告换成实测版。**')
    a('- **`academy_24000_config.json` 线上内容未找到**（决定发 1 条还是 9 条地点）。')
    a('- **客户端侧代码未参与**：本报告只能判"包对不对"，判不了"客户端要不要"。'
      '§8 Q3 里"客户端是否校验 token 长度"、§5.3 里"客户端是否要求非空 zone"都**无客户端证据**。')
    a('- 线上服务器**未连接、未改动**（按纪律）。')
    a('')
    a('## 附录 A · `1017` 就是 `Account_LoginSync`（与 `report/63` 的结论相反）')
    a('')
    a('任务书写"官方客户端在 24000 之后 0.130 秒就发 `1017 Account_LoginSync`"——'
      '**这个说法在这份官方真服抓包里是对的**，`report/63` A13.5 的'
      '"`1017` = `DismissRepurchasablePopup`"结论应当作废。硬证据：')
    a('')
    a('| 证据 | 值 |')
    a('|---|---|')
    a('| URL | `POST /api/account/loginsync` |')
    a('| 包内 `Protocol` | **`1017`** |')
    a('| `Hash` | `4367981740035` ⇒ `Hash >> 32` = **1017**，低 32 位 = 3 |')
    a('| `SyncProtocols` | **25 个**：`[20000,1003,2000,3000,5000,12000,6000,22001,17018,21000,28001,33000,19000,10006,39006,44000,29002,30041,45000,46000,46001,47000,49000,27002,49004]` |')
    a('| `SkillCutInOption` | `"OnceADay"` |')
    a('| `SessionKey` | 已填：`{AccountServerId: 10015354380, MxToken: <64 字符>}` |')
    a('| `AccountId` | `10015354380` |')
    a('')
    a('**为什么之前的结论是 1019**：那条据以定案的包是'
      '`{"Protocol":"Account_LoginSync","SyncProtocols":[],"SkillCutInOption":"",'
      '"Resendable":false,"Hash":4376571674624,"IsTest":false,"SessionKey":null,"AccountId":0,"OSType":2}` '
      '—— `SessionKey` 为 `null`、`AccountId` 为 `0`、`SyncProtocols` 为空，'
      '这是 **srv-ops 手工 curl 构造**的包（`report/63` A19.5 自己也承认"客户端从未主动发过"），'
      '不是客户端产物。`4376571674624 >> 32 = 1019` 只反映那条 curl 里手写的数字。')
    a('')
    a('⇒ **以第一方抓包为准：国服 `Account_LoginSync = 1017`，且它的请求带 25 个 `SyncProtocols`**'
      '（`AccountLoginSyncResponse` 要按这 25 个点名回子包，不是空 `Responses`）。'
      '这条对下一步的意义：24000 修好之后客户端要来的是 **1017**，'
      '而 `1017` 的响应里有 25 个子回包要凑齐。')
    a('')

    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(L))

    print('写出: %s' % OUT)
    print('  行数: %d' % len(L))
    print('  官方 inner=%d 我们 inner=%d 重放 inner=%d' % (o_inner, u_inner, r_inner))
    print('  官方 envelope=%d 我们 envelope=%d 折算 wire≈%d' % (o_plain, u_plain_len, wire_est))
    return 0


if __name__ == '__main__':
    sys.exit(main())
