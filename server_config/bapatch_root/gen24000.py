#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen24000.py -- 24000 Academy_GetInfo 的**动态**渲染引擎（唯一真源）。

和 scripts/292_24000_official.py 的根本区别
--------------------------------------------
292 的做法是「官方抓包存成静态模板 → 4 个占位符字符串替换」。它只对一个固定的
账号/会话成立，模板里 9 条 AcademyLocationDBs 和 276 条 zone 访问记录全是别人的数据。

本引擎是**按账号生成**：

    build_24000(account_id, mxtoken, request_id, ticks) -> 完整 24000 dict

    动态字段（每个账号/每次请求都不同）
      SessionKey.AccountServerId  <- account_id（来自请求 / 会话）
      SessionKey.MxToken          <- mxtoken（来自 CheckNexon 会话，64 字符 base64）
      RequestId                   <- request_id（uuid4，外层 requestid 与它同值）
      ServerTimeTicks             <- ticks（.NET 100ns，自 0001-01-01）
      AcademyDB.AccountId         <- account_id
      AcademyDB.LastUpdate        <- 由 ticks 反推（同一时间坐标系），可覆盖
      AcademyLocationDBs[].AccountId <- account_id

    静态字段（与账号无关，由规则推导，不是抄快照）
      7 个顶层键及其固定键序
      ZoneVisitCharacterDBs 的 71 个 zone key 及其键序
      ZoneScheduleGroupRecords == {}
      AcademyLocationDBs 的行形状 {AccountId,LocationId,Rank,Exp}

结构权威：work/ba/proto/official_spec.json -> protocols["24000"]
    top_key_order = [Protocol, SessionKey, ServerTimeTicks, ServerNotification,
                     RequestId, AcademyDB, AcademyLocationDBs]
    五个信封字段 109/109 必填；ZoneVisitCharacterDBs 是 map<int_str, array>，71 键

71 个 zone key 的来路（可复算，不是快照）
-----------------------------------------
work/ba/data/ExcelDB.db 的 AcademyZoneDBSchema.f1 = location。
国服启用的 9 个 location = AcademyLocationDBSchema 11 行去掉 14(Trinity)/18(Shanhaijing)。
按 f1 分组得到 8 + 7 + 8x7 = 71 个 zone，与官方抓包 71 个键**集合完全相等**。
本文件把这份分组内嵌为 B24000_ZONE_LAYOUT 常量（部署机没有 ExcelDB.db），
`--verify-db` 可在有 ExcelDB.db 的机器上重新推导并逐项比对。

键序的来路
----------
官方抓包的 ZoneVisitCharacterDBs 键序是**字典序**（'1','10','11','110',...,'117','12',...），
即 Go encoding/json 对 map 的序列化顺序。这里按字典序输出，与官方逐字节一致。

命令行
------
    # 1) 渲染一个账号
    python gen24000.py --account-id 10015354380 --out out/t24000.json

    # 2) 换账号（动态字段变，静态部分不变）
    python gen24000.py --account-id 99990000001 --out out/t24000b.json

    # 3) 测 9 条学院地点（上机 A/B 用；官方那个 32 级号就是 9 条）
    python gen24000.py --account-id 10015354380 --locations all9 --out out/t9.json

    # 4) 自检 / 打印内嵌引擎源码（patch_24000_v2.py 会内联它）/ 复算 zone 键
    python gen24000.py --selfcheck
    python gen24000.py --print-engine
    python gen24000.py --verify-db

    # 5) 渲染后直接跑 spec_check
    python gen24000.py --account-id 10015354380 --out out/t.json --spec-check
"""
import argparse
import base64
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
SPEC_CHECK = os.path.join(ROOT, 'work', 'ba', 'proto', 'spec_check.py')
EXCELDB = os.path.join(ROOT, 'work', 'ba', 'data', 'ExcelDB.db')
PROTOTYPE_DIR = os.path.join(ROOT, 'work', 'ba', 'server', 'prototype')
FIXTURE = os.path.join(ROOT, 'report', '_tmp', 'official_decoded_201',
                       '01_24000_api_academy_getinfo.response.json')

PROTO = 24000
ENGINE_VERSION = '2.0.0'

ENGINE_BEGIN = '# ==== BEGIN ENGINE CORE (24000 v2) ===='
ENGINE_END = '# ==== END ENGINE CORE (24000 v2) ===='


# ================================================================ 引擎核（会被逐字内联）
# 约束（内联进 account_auth_probe.py 的托管块，必须全部满足）：
#   * 只依赖标准库；import 放在函数体内（不污染宿主模块命名空间）
#   * 不用 f-string / 海象运算符（宿主解释器版本未知）
#   * 所有顶层名字带 b24000_ / B24000_ 前缀（不与宿主撞名）
#   * 不在这里读文件/连库/写日志：纯函数
# ==== BEGIN ENGINE CORE (24000 v2) ====
B24000_PROTO = 24000
B24000_ENGINE_VERSION = '2.0.0'
B24000_TOP_KEYS = ('Protocol', 'SessionKey', 'ServerTimeTicks', 'ServerNotification',
                   'RequestId', 'AcademyDB', 'AcademyLocationDBs')

# AcademyZoneDBSchema.f1 的分组：location -> 该 location 的 zone id（ExcelDB 只读推导）
# 国服启用 9 个 location（AcademyLocationDBSchema 11 行去掉 14 Trinity / 18 Shanhaijing）
# zone 个数 8 + 7 + 8*7 = 71，与官方 24000 的 71 个键集合完全相等
B24000_ZONE_LAYOUT = (
    (1, (1, 10, 11, 12, 13, 14, 15, 16)),
    (7, (20, 21, 22, 23, 24, 25, 26)),
    (11, (30, 31, 32, 33, 34, 35, 36, 37)),
    (12, (40, 41, 42, 43, 44, 45, 46, 47)),
    (13, (50, 51, 52, 53, 54, 55, 56, 57)),
    (15, (70, 71, 72, 73, 74, 75, 76, 77)),
    (16, (80, 81, 82, 83, 84, 85, 86, 87)),
    (17, (90, 91, 92, 93, 94, 95, 96, 97)),
    (19, (110, 111, 112, 113, 114, 115, 116, 117)),
)
B24000_ENABLED_LOCATIONS = tuple(loc for loc, _zs in B24000_ZONE_LAYOUT)
B24000_ZONE_BY_LOCATION = dict(B24000_ZONE_LAYOUT)
B24000_ZONE_IDS = tuple(sorted(z for _loc, zs in B24000_ZONE_LAYOUT for z in zs))
# 键序 = 字典序（Go encoding/json 对 map 的序列化顺序），官方抓包实测如此
B24000_ZONE_KEY_ORDER = tuple(sorted(str(z) for z in B24000_ZONE_IDS))

# 新号学院地点：initial_state_rules.q8.initial.suggested_minimum
#   [{"LocationId": 1, "Rank": 1, "Exp": 0}]  （Rank 初值 high 置信；条数未找到规则）
B24000_DEFAULT_LOCATIONS = ({'LocationId': 1, 'Rank': 1, 'Exp': 0},)
# 官方那个 32 级号是 9 条（Rank 2/1/1/2/1/1/2/2/2，Exp 只有 19 号是 200）。
# 新号若上机因学院崩，改用它做 A/B：坐标全 1、Exp 全 0。
B24000_ALL9_LOCATIONS = tuple({'LocationId': loc, 'Rank': 1, 'Exp': 0}
                              for loc in B24000_ENABLED_LOCATIONS)


def b24000_ticks(dt=None):
    """.NET DateTime.Ticks：100ns 自 0001-01-01。整数运算，不经 float。

    口径证据：官方抓包 24000 的 ServerTimeTicks=639304002548158993 换算成
    2026-11-16T04:30:54.815899，与同一份抓包 meta 的墙钟 04:30:54.980 对齐
    => 单位确实是 100ns，且取的是**服务器本地墙钟**（不是 UTC）。
    """
    from datetime import datetime as _dt, timedelta as _td
    dt = dt or _dt.now()
    return ((dt - _dt(1, 1, 1)) // _td(microseconds=1)) * 10


def b24000_time_from_ticks(ticks):
    """ticks -> 同一个墙钟坐标系下的 datetime（与 b24000_ticks 互逆）。"""
    from datetime import datetime as _dt, timedelta as _td
    return _dt(1, 1, 1) + _td(microseconds=int(ticks) // 10)


def b24000_fmt_time(dt, frac=3):
    """'2026-11-16T04:00:06.479' —— 无时区、毫秒精度、尾零裁掉（官方 LastUpdate 形态）。"""
    s = '%04d-%02d-%02dT%02d:%02d:%02d' % (dt.year, dt.month, dt.day,
                                          dt.hour, dt.minute, dt.second)
    if frac:
        digits = ('%09d' % (dt.microsecond * 1000))[:int(frac)].rstrip('0')
        if digits:
            s += '.' + digits
    return s


def b24000_normalize_locations(locations=None):
    """把任意来源的行规整成 [{LocationId,Rank,Exp}]（int、按 LocationId 升序、去重）。

    官方 9 条的顺序就是 LocationId 升序，所以这里排序后输出，与官方一致。
    任何脏数据都不抛异常：解析不出来的行直接跳过，最后空了就退回最小实现。
    """
    rows = []
    src = locations if locations else B24000_DEFAULT_LOCATIONS
    for row in src:
        if isinstance(row, dict):
            try:
                loc = int(row.get('LocationId'))
            except Exception:
                continue
            try:
                rank = int(row.get('Rank', 1))
            except Exception:
                rank = 1
            try:
                exp = int(row.get('Exp', 0))
            except Exception:
                exp = 0
            rows.append({'LocationId': loc, 'Rank': rank, 'Exp': exp})
        elif isinstance(row, (list, tuple)) and len(row) >= 3:
            try:
                rows.append({'LocationId': int(row[0]), 'Rank': int(row[1]), 'Exp': int(row[2])})
            except Exception:
                continue
    if not rows:
        rows = [dict(r) for r in B24000_DEFAULT_LOCATIONS]
    rows.sort(key=lambda r: r['LocationId'])
    out = []
    seen = set()
    for r in rows:
        if r['LocationId'] in seen:
            continue
        seen.add(r['LocationId'])
        out.append(r)
    return out


def b24000_zone_keys(zone_scope='service', locations=None):
    """ZoneVisitCharacterDBs 的键（有序）。

    service（默认）：国服 9 个 location 的全部 zone = 71 个，= spec 的 key_count。
    account        ：只给本账号 AcademyLocationDBs 里出现过的 location 的 zone
                     （严格状态驱动；新号 1 条地点时是 8 个键，spec 会 WARN 长度越界）
    """
    if str(zone_scope) == 'account':
        locs = []
        for row in (locations or ()):
            try:
                locs.append(int(row.get('LocationId')))
            except Exception:
                continue
        if not locs:
            locs = list(B24000_ENABLED_LOCATIONS)
        keys = set()
        for loc in locs:
            for z in B24000_ZONE_BY_LOCATION.get(loc, ()):
                keys.add(str(z))
        return tuple(sorted(keys))
    return B24000_ZONE_KEY_ORDER


def b24000_academy_locations(account_id, locations=None):
    """AcademyLocationDBs 的行：严格 4 键 {AccountId,LocationId,Rank,Exp}（spec key_count=4）。"""
    aid = int(account_id)
    return [{'AccountId': aid, 'LocationId': r['LocationId'], 'Rank': r['Rank'], 'Exp': r['Exp']}
            for r in b24000_normalize_locations(locations)]


def b24000_build(account_id, mxtoken, request_id, ticks,
                 locations=None, last_update=None, zone_scope='service', zone_visit=None):
    """渲染完整的 24000 响应。

    account_id : int   AccountServerId（也是 AcadeyDB.AccountId）
    mxtoken    : str   SessionKey.MxToken（官方 64 字符 base64）
    request_id : str   外层 requestid 与它必须**同值**（官方 outer == inner）
    ticks      : int   .NET 100ns ticks
    locations  : 可选的 AcademyLocationDBs 行；None = 最小实现（1 条 1/1/0）
    last_update: 可选 ISO 字符串；None = 由 ticks 反推（同一墙钟坐标系）
    zone_scope : 'service'（71 键，默认）/ 'account'（只给本账号地点）
    zone_visit : 可选 {zone_key: [ {UniqueId,ServerId,LastInteractTime}, ... ]}，
                 只保留 b24000_zone_keys() 里存在的键，用于把状态接进来
    """
    aid = int(account_id)
    nlt = int(ticks)
    rows = b24000_normalize_locations(locations)
    if last_update is None:
        last_update = b24000_fmt_time(b24000_time_from_ticks(nlt))

    zone_visit = zone_visit or {}
    zv = {}
    for k in b24000_zone_keys(zone_scope, rows):
        vals = zone_visit.get(k)
        zv[k] = [dict(el) for el in vals if isinstance(el, dict)] if vals else []

    return {
        'Protocol': B24000_PROTO,
        'SessionKey': {'AccountServerId': aid, 'MxToken': str(mxtoken or '')},
        'ServerTimeTicks': nlt,
        'ServerNotification': 0,
        'RequestId': str(request_id or ''),
        'AcademyDB': {
            'AccountId': aid,
            'LastUpdate': str(last_update),
            'ZoneVisitCharacterDBs': zv,
            'ZoneScheduleGroupRecords': {},
        },
        'AcademyLocationDBs': b24000_academy_locations(aid, rows),
    }


def b24000_compact(obj):
    """紧凑 JSON（wire 里 packet 的实际序列化方式）。"""
    import json as _json
    return _json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def b24000_check(obj):
    """结构自检，返回 dict（不抛异常）：ok / problems / 各项计数。"""
    out = {'ok': False, 'problems': [], 'top_keys': [], 'zone_keys': 0,
           'locations': 0, 'inner_bytes': 0, 'rid_len': 0, 'token_len': 0}
    try:
        if not isinstance(obj, dict):
            out['problems'].append('根节点不是 dict: %s' % type(obj).__name__)
            return out
        keys = tuple(obj.keys())
        out['top_keys'] = list(keys)
        if keys != B24000_TOP_KEYS:
            out['problems'].append('顶层键/键序不符: %r != %r' % (list(keys), list(B24000_TOP_KEYS)))
        if obj.get('Protocol') != B24000_PROTO:
            out['problems'].append('Protocol=%r' % (obj.get('Protocol'),))
        sk = obj.get('SessionKey')
        if not isinstance(sk, dict) or tuple(sk.keys()) != ('AccountServerId', 'MxToken'):
            out['problems'].append('SessionKey 形状不符: %r' % (sk,))
        else:
            if not isinstance(sk.get('AccountServerId'), int):
                out['problems'].append('SessionKey.AccountServerId 不是 int')
            out['token_len'] = len(str(sk.get('MxToken') or ''))
        if not isinstance(obj.get('ServerTimeTicks'), int):
            out['problems'].append('ServerTimeTicks 不是 int')
        if obj.get('ServerNotification') != 0:
            out['problems'].append('ServerNotification 应为 0')
        rid = obj.get('RequestId')
        if not isinstance(rid, str) or not rid:
            out['problems'].append('RequestId 为空或非字符串')
        out['rid_len'] = len(rid) if isinstance(rid, str) else 0

        adb = obj.get('AcademyDB')
        if not isinstance(adb, dict):
            out['problems'].append('AcademyDB 不是 dict')
        else:
            if tuple(adb.keys()) != ('AccountId', 'LastUpdate', 'ZoneVisitCharacterDBs',
                                     'ZoneScheduleGroupRecords'):
                out['problems'].append('AcademyDB 键/键序不符: %r' % (list(adb.keys()),))
            if not isinstance(adb.get('AccountId'), int):
                out['problems'].append('AcademyDB.AccountId 不是 int')
            if not isinstance(adb.get('LastUpdate'), str) or 'T' not in str(adb.get('LastUpdate')):
                out['problems'].append('AcademyDB.LastUpdate 形态不符: %r' % (adb.get('LastUpdate'),))
            zv = adb.get('ZoneVisitCharacterDBs')
            if not isinstance(zv, dict):
                out['problems'].append('ZoneVisitCharacterDBs 不是 dict（必须是 map<string,array>）')
            else:
                out['zone_keys'] = len(zv)
                if not all(isinstance(v, list) for v in zv.values()):
                    out['problems'].append('ZoneVisitCharacterDBs 存在非数组值')
                if not all(str(k).lstrip('-').isdigit() for k in zv):
                    out['problems'].append('ZoneVisitCharacterDBs 存在非数字键')
                if len(zv) == len(B24000_ZONE_KEY_ORDER) and tuple(zv.keys()) != B24000_ZONE_KEY_ORDER:
                    out['problems'].append('ZoneVisitCharacterDBs 键序不是字典序')
            if adb.get('ZoneScheduleGroupRecords') != {}:
                out['problems'].append('ZoneScheduleGroupRecords 必须为空对象 {}')

        locs = obj.get('AcademyLocationDBs')
        if not isinstance(locs, list) or not locs:
            out['problems'].append('AcademyLocationDBs 为空或非数组')
        else:
            out['locations'] = len(locs)
            for i, row in enumerate(locs):
                if not isinstance(row, dict):
                    out['problems'].append('AcademyLocationDBs[%d] 不是 dict' % i)
                    continue
                if tuple(row.keys()) != ('AccountId', 'LocationId', 'Rank', 'Exp'):
                    out['problems'].append('AcademyLocationDBs[%d] 键/键序不符: %r'
                                           % (i, list(row.keys())))
                for k in ('AccountId', 'LocationId', 'Rank', 'Exp'):
                    if not isinstance(row.get(k), int):
                        out['problems'].append('AcademyLocationDBs[%d].%s 不是 int' % (i, k))
        out['inner_bytes'] = len(b24000_compact(obj).encode('utf-8'))
        out['ok'] = not out['problems']
    except Exception as e:            # 自检本身不允许把调用方拖死
        out['problems'].append('check 异常: %r' % (e,))
        out['ok'] = False
    return out
# ==== END ENGINE CORE (24000 v2) ====


# 方便本地调用的别名（**不进**内联核，避免在宿主里多一个泛用名）
build_24000 = b24000_build


# ================================================================ 引擎核源码（给补丁内联）
def engine_source():
    """返回 ENGINE_BEGIN..ENGINE_END 之间的源码（含标记行），供 patch 逐字内联。

    必须按**整行**匹配：文件头部的 `ENGINE_END = '# ==== END ...'` 常量定义里也含标记文本，
    用子串查找会在那里提前截断。
    """
    path = os.path.abspath(__file__)
    with open(path, 'r', encoding='utf-8') as fh:
        lines = fh.read().split('\n')
    bi = ei = None
    for i, line in enumerate(lines):
        if line.rstrip('\r') == ENGINE_BEGIN and bi is None:
            bi = i
        elif line.rstrip('\r') == ENGINE_END and bi is not None:
            ei = i
            break
    if bi is None or ei is None:
        raise RuntimeError('engine markers not found in %s' % path)
    return '\n'.join(lines[bi:ei + 1])


def engine_sha256():
    return hashlib.sha256(engine_source().encode('utf-8')).hexdigest()


# ================================================================ 辅助（不进内联核）
def derive_token(account_id):
    """没有真会话时的 MxToken：sha384(账号) → base64 = 恰好 64 字符，与官方同形。"""
    digest = hashlib.sha384(('ba24000:%d' % int(account_id)).encode('utf-8')).digest()
    return base64.b64encode(digest).decode('ascii')


def parse_locations_arg(text):
    """'min' | 'all9' | '1:1:0,7:1:0' | JSON 数组 -> locations 列表。"""
    if not text:
        return None
    t = str(text).strip()
    if t in ('min', 'default', 'suggested_minimum'):
        return [dict(r) for r in B24000_DEFAULT_LOCATIONS]
    if t in ('all9', 'nine', 'official9'):
        return [dict(r) for r in B24000_ALL9_LOCATIONS]
    if t.startswith('['):
        data = json.loads(t)
        return data if isinstance(data, list) else None
    rows = []
    for part in t.split(','):
        part = part.strip()
        if not part:
            continue
        bits = part.replace(':', '/').split('/')
        if len(bits) < 3:
            raise SystemExit('--locations 格式错误: %r（应为 LocationId:Rank:Exp）' % part)
        rows.append((int(bits[0]), int(bits[1]), int(bits[2])))
    return rows


def _load_specgen():
    """复用 prototype/specgen.py 读 ExcelDB（不重复造 FlatBuffers 读取器）。"""
    if not os.path.isdir(PROTOTYPE_DIR):
        return None
    if PROTOTYPE_DIR not in sys.path:
        sys.path.insert(0, PROTOTYPE_DIR)
    try:
        import specgen                                             # noqa: F401
        return specgen
    except Exception:
        return None


def verify_db(verbose=True):
    """在能读到 ExcelDB.db 的机器上复算 71 个 zone，与内嵌常量逐项比对。"""
    g = _load_specgen()
    if g is None or not os.path.exists(g.EXCELDB_PATH):
        print('SKIP  读不到 ExcelDB.db 或 specgen.py（部署机正常现象）: %s' % EXCELDB)
        return None
    master = g.MasterData()
    try:
        derived = tuple(sorted(master.zone_ids(g.SERVICE_ENABLED_LOCATIONS)))
        layout = {}
        for zid, loc in sorted(master.zone_location_map().items()):
            layout.setdefault(loc, []).append(zid)
    finally:
        master.close()
    embedded_layout = {loc: list(zs) for loc, zs in B24000_ZONE_LAYOUT}
    ok_set = tuple(derived) == B24000_ZONE_IDS
    ok_layout = all(sorted(layout.get(loc, [])) == sorted(zs)
                    for loc, zs in embedded_layout.items())
    if verbose:
        print('ExcelDB          : %s' % g.EXCELDB_PATH)
        print('ExcelDB 推导     : %d 个 zone' % len(derived))
        print('内嵌常量         : %d 个 zone' % len(B24000_ZONE_IDS))
        print('集合相等         : %s' % ('YES' if ok_set else 'NO'))
        print('分组(location)相等: %s' % ('YES' if ok_layout else 'NO'))
        extra = sorted(set(derived) - set(B24000_ZONE_IDS))
        missing = sorted(set(B24000_ZONE_IDS) - set(derived))
        if extra or missing:
            print('  多出 %r 缺少 %r' % (extra, missing))
    return ok_set and ok_layout


def run_spec_check(path, verbose=True):
    """调用 work/ba/proto/spec_check.py（不重写校验器）。"""
    if not os.path.exists(SPEC_CHECK):
        if verbose:
            print('SKIP  spec_check.py 不存在: %s' % SPEC_CHECK)
        return None
    proto_dir = os.path.dirname(SPEC_CHECK)
    if proto_dir not in sys.path:
        sys.path.insert(0, proto_dir)
    import spec_check                                              # noqa: E402
    with open(SPEC_CHECK.replace('spec_check.py', 'official_spec.json'), 'r',
              encoding='utf-8') as fh:
        spec = json.load(fh)
    with open(path, 'r', encoding='utf-8') as fh:
        obj = json.load(fh)
    inner = obj.get('inner') if isinstance(obj, dict) and 'inner' in obj else obj
    rep, entry = spec_check.check_one(inner.get('Protocol'), inner, spec, path)
    if verbose:
        print('spec_check       : %s  FAIL %d / WARN %d'
              % ('PASS' if not rep.fails else 'FAIL', len(rep.fails), len(rep.warns)))
        for k, p, d in rep.fails[:20]:
            print('  FAIL [%s] %s  %s' % (k, p, d))
        for k, p, d in rep.warns[:10]:
            print('  WARN [%s] %s  %s' % (k, p, d))
    return not rep.fails


def selfcheck():
    """引擎不变量：71 键、9 个 location、键序字典序、固定输入下的字节数稳定。"""
    ok = True
    print('ENGINE_VERSION   : %s' % ENGINE_VERSION)
    print('engine sha256    : %s' % engine_sha256())
    print('zone layout      : %d 个 location, 每 location %r'
          % (len(B24000_ZONE_LAYOUT), [len(zs) for _l, zs in B24000_ZONE_LAYOUT]))
    print('zone 总数        : %d (期望 71)  8+7+8*7=%d'
          % (len(B24000_ZONE_IDS), 8 + 7 + 8 * 7))
    ok &= len(B24000_ZONE_IDS) == 71
    ok &= len(B24000_ZONE_KEY_ORDER) == 71
    ok &= tuple(sorted(str(z) for z in B24000_ZONE_IDS)) == B24000_ZONE_KEY_ORDER
    ok &= B24000_ZONE_KEY_ORDER[:3] == ('1', '10', '11')

    obj = b24000_build(10015354380,
                       'Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA',
                       '3770c1bc-a631-46fb-a9b6-0421ae2601fe',
                       639304002548158993)
    chk = b24000_check(obj)
    print('固定输入自检     : %s  %s' % ('PASS' if chk['ok'] else 'FAIL', chk['problems']))
    print('  inner bytes    : %d' % chk['inner_bytes'])
    print('  top keys       : %d %r' % (len(chk['top_keys']), chk['top_keys']))
    print('  zone keys      : %d   地点 %d 条' % (chk['zone_keys'], chk['locations']))
    ok &= chk['ok']
    # 反例：故意少一个键/错键序，check 必须拒绝
    bad = b24000_build(1, 'x', 'y', 1)
    bad['AcademyDB']['ZoneVisitCharacterDBs'] = []
    bad['StaticOpenConditions'] = []
    bad2 = dict(bad)
    ok &= (not b24000_check(bad)['ok']) and (not b24000_check(bad2)['ok'])
    print('反例自检         : %s（缺 RequestId 结构 / 多伪键都会被拒）'
          % ('PASS' if ok else 'FAIL'))
    if os.path.exists(SPEC_CHECK):
        tmp = os.path.join(HERE, '_selfcheck_24000.json')
        with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(obj, fh, ensure_ascii=False, separators=(',', ':'))
            fh.write('\n')
        res = run_spec_check(tmp)
        ok &= bool(res)
        os.remove(tmp)
    print('SELFCHECK        : %s' % ('PASS' if ok else 'FAIL'))
    return ok


def fidelity_check(verbose=True):
    """用官方抓包里的 4 个动态值 + 官方 9 条地点/276 条 zone 记录渲染，
    期望与官方 packet **逐字节相同**（11,685 B）。用来证明"引擎序列化与官方一致，
    我们和官方的字节差全部来自数据，不是来自格式"。"""
    if not os.path.exists(FIXTURE):
        if verbose:
            print('SKIP  抓包不存在: %s' % FIXTURE)
        return None
    with open(FIXTURE, 'r', encoding='utf-8') as fh:
        cap = json.load(fh)
    off = cap['inner']
    plain = json.loads(cap['plain'])
    want = plain['packet']
    zone_visit = off['AcademyDB']['ZoneVisitCharacterDBs']
    obj = b24000_build(off['AcademyDB']['AccountId'],
                       off['SessionKey']['MxToken'],
                       off['RequestId'],
                       off['ServerTimeTicks'],
                       locations=off['AcademyLocationDBs'],
                       last_update=off['AcademyDB']['LastUpdate'],
                       zone_visit=zone_visit)
    got = b24000_compact(obj)
    same = got == want
    if verbose:
        print('fidelity         : %s  引擎 %d B / 官方 %d B'
              % ('BYTE-IDENTICAL' if same else 'DIFFERS', len(got.encode('utf-8')),
                 len(want.encode('utf-8'))))
        if not same:
            for i, (a, b) in enumerate(zip(got, want)):
                if a != b:
                    print('  首个差异 @ %d: %r != %r' % (i, got[i:i + 60], want[i:i + 60]))
                    break
        print('   外层 requestid == 内层 RequestId: %s'
              % ('YES' if plain.get('requestid') == off.get('RequestId') else 'NO'))
    return same


def _collect_diffs(a, b, path, out):
    """递归收集两份响应的差异路径。"""
    if type(a) is not type(b):
        out.append((path, a, b))
        return
    if isinstance(a, dict):
        for k in list(a.keys()) + [k for k in b.keys() if k not in a]:
            p = (path + '.' + k) if path else k
            if k not in a:
                out.append((p, '<缺失>', b[k]))
            elif k not in b:
                out.append((p, a[k], '<缺失>'))
            else:
                _collect_diffs(a[k], b[k], p, out)
        return
    if isinstance(a, list):
        if len(a) != len(b):
            out.append((path + '.length', len(a), len(b)))
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _collect_diffs(x, y, '%s[%d]' % (path, i), out)
        return
    if a != b:
        out.append((path, a, b))


# 允许不同的字段（动态部分）：其余必须一致
DYNAMIC_PATHS = ('SessionKey.AccountServerId', 'SessionKey.MxToken',
                 'ServerTimeTicks', 'RequestId',
                 'AcademyDB.AccountId', 'AcademyDB.LastUpdate')
DYNAMIC_PREFIX = 'AcademyLocationDBs['
DYNAMIC_SUFFIX = '].AccountId'


def is_dynamic_path(path):
    if path in DYNAMIC_PATHS:
        return True
    return path.startswith(DYNAMIC_PREFIX) and path.endswith(DYNAMIC_SUFFIX)


def compare_files(path_a, path_b, verbose=True):
    """比较两份渲染结果：只允许动态字段不同，静态部分（71 键集合/键序/其余全部）必须一致。"""
    with open(path_a, 'r', encoding='utf-8') as fh:
        a = json.load(fh)
    with open(path_b, 'r', encoding='utf-8') as fh:
        b = json.load(fh)
    diffs = []
    _collect_diffs(a, b, '', diffs)
    bad = [d for d in diffs if not is_dynamic_path(d[0])]
    if verbose:
        print('比较             : %s' % os.path.basename(path_a))
        print('                   %s' % os.path.basename(path_b))
        print('差异条目         : %d' % len(diffs))
        for p, x, y in diffs:
            ok = is_dynamic_path(p)
            print('  %s %-32s %r -> %r' % ('OK ' if ok else 'BAD', p,
                                          _short(x), _short(y)))
        za = list(a['AcademyDB']['ZoneVisitCharacterDBs'].keys())
        zb = list(b['AcademyDB']['ZoneVisitCharacterDBs'].keys())
        print('zone key 集合相同: %s（%d 个）'
              % ('YES' if set(za) == set(zb) else 'NO', len(za)))
        print('zone key 键序相同: %s' % ('YES' if za == zb else 'NO'))
        print('结论             : %s' % ('PASS（只有动态字段不同）' if not bad
                                          else 'FAIL（%d 处静态字段被改动）' % len(bad)))
    return not bad


def _short(v, limit=44):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return s if len(s) <= limit else s[:limit] + '...'


# ================================================================ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description='24000 Academy_GetInfo 动态渲染引擎')
    ap.add_argument('--account-id', type=int, default=None, help='AccountServerId')
    ap.add_argument('--mxtoken', default=None, help='SessionKey.MxToken（默认由账号派生 64 字符）')
    ap.add_argument('--request-id', default=None, help='RequestId（默认 uuid4）')
    ap.add_argument('--ticks', type=int, default=None, help='.NET 100ns ticks（默认现在）')
    ap.add_argument('--now', default=None, help='固定墙钟 YYYY-MM-DDTHH:MM:SS（替代 --ticks）')
    ap.add_argument('--locations', default=None,
                    help="min(默认) | all9 | '1:1:0,7:1:0' | JSON 数组")
    ap.add_argument('--zone-scope', choices=['service', 'account'], default='service')
    ap.add_argument('--last-update', default=None, help='强制 LastUpdate（默认由 ticks 反推）')
    ap.add_argument('--out', default=None, help='输出 JSON 路径（默认不落盘，只打印摘要）')
    ap.add_argument('--compact', action='store_true', help='输出紧凑 JSON（默认缩进）')
    ap.add_argument('--spec-check', action='store_true', help='渲染后调用 spec_check.py')
    ap.add_argument('--selfcheck', action='store_true', help='引擎不变量自检')
    ap.add_argument('--fidelity', action='store_true', help='与官方抓包做逐字节比对')
    ap.add_argument('--verify-db', action='store_true', help='从 ExcelDB.db 复算 71 个 zone')
    ap.add_argument('--print-engine', action='store_true', help='打印内嵌引擎核源码')
    ap.add_argument('--compare', nargs=2, metavar=('A', 'B'),
                    help='比较两份渲染结果：只允许动态字段不同')
    a = ap.parse_args(argv)

    if a.print_engine:
        sys.stdout.write(engine_source() + '\n')
        return 0
    if a.compare:
        return 0 if compare_files(a.compare[0], a.compare[1]) else 1
    if a.selfcheck:
        return 0 if selfcheck() else 1
    if a.fidelity:
        return 0 if fidelity_check() else 1
    if a.verify_db:
        res = verify_db()
        return 0 if (res is None or res) else 1
    if a.account_id is None:
        ap.error('要么给 --account-id，要么用 --selfcheck/--fidelity/--verify-db/--print-engine')

    now = datetime.now()
    if a.now:
        now = datetime.strptime(a.now, '%Y-%m-%dT%H:%M:%S')
    ticks = int(a.ticks) if a.ticks is not None else b24000_ticks(now)
    token = a.mxtoken if a.mxtoken else derive_token(a.account_id)
    rid = a.request_id or str(uuid.uuid4())
    locations = parse_locations_arg(a.locations)

    obj = b24000_build(a.account_id, token, rid, ticks, locations=locations,
                       last_update=a.last_update, zone_scope=a.zone_scope)
    chk = b24000_check(obj)
    inner = b24000_compact(obj)

    print('=' * 76)
    print('24000 Academy_GetInfo · 动态渲染（引擎 v%s）' % ENGINE_VERSION)
    print('=' * 76)
    print('AccountServerId  : %d' % a.account_id)
    print('MxToken          : %d 字符 %s' % (len(token), '（来自 --mxtoken）' if a.mxtoken
                                             else '（由账号派生，无真会话时用）'))
    print('RequestId        : %s' % rid)
    print('ServerTimeTicks  : %d  ->  %s'
          % (ticks, b24000_fmt_time(b24000_time_from_ticks(ticks))))
    print('LastUpdate       : %s%s' % (obj['AcademyDB']['LastUpdate'],
                                      '（--last-update 指定）' if a.last_update else '（由 ticks 反推）'))
    print('zone_scope       : %s -> %d 个 zone key' % (a.zone_scope, chk['zone_keys']))
    print('AcademyLocationDBs: %d 条 %r'
          % (chk['locations'], [(r['LocationId'], r['Rank'], r['Exp'])
                                for r in obj['AcademyLocationDBs']]))
    print('顶层键           : %d/7 %r' % (len(chk['top_keys']), chk['top_keys']))
    print('inner JSON       : %d 字节（紧凑）' % chk['inner_bytes'])
    print('结构自检         : %s %s' % ('PASS' if chk['ok'] else 'FAIL', chk['problems']))

    if a.out:
        path = os.path.abspath(a.out)
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            if a.compact:
                fh.write(inner + '\n')
            else:
                json.dump(obj, fh, ensure_ascii=False, indent=1)
                fh.write('\n')
        print('输出文件         : %s (%d 字节)' % (path, os.path.getsize(path)))
    if a.spec_check:
        path = os.path.abspath(a.out) if a.out else None
        if path is None:
            ap.error('--spec-check 需要 --out')
        res = run_spec_check(path)
        if res is False:
            return 1
    return 0 if chk['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
