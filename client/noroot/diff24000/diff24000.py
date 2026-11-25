#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diff24000.py -- 24000 Academy_GetInfo 响应的**逐字段递归对比**工具。

只读：不修改任何输入文件，只在 --csv/--md 指定的路径写输出。

用法
----
    # 官方抓包（cmp 用 inner 字段）vs 我们的一份渲染
    python diff24000.py --official report\\_tmp\\official_decoded_201\\01_24000_api_academy_getinfo.response.json ^
                        --ours     work\\ba\\noroot\\diff24000\\our_min.json ^
                        --csv      work\\ba\\noroot\\diff24000\\diff_A.csv

    # 只做单边体检（Q1-Q5），不比较
    python diff24000.py --official <cap>.json --check-only

输出列（任务书要求）
------------------
    路径 | 官方值/类型 | 我们的值/类型 | 一致? | 严重度

严重度分级
----------
    P0-结构  键缺失/多余、类型不符、键序不符、null 形态不符  -> 客户端反序列化直接抛异常
    P0-格式  字符串长度/编码/数值量级不符（MxToken 非 64、ticks 位数不对、时间格式不对）
    P1-语义  集合长度官方非空而我们为空（zone 角色、地点条数）  -> 业务逻辑可能崩/空指针
    P2-动态  值不同但类型与格式正确，且按设计就该逐账号/逐请求不同
    OK       完全一致
"""
import argparse
import base64
import csv
import io
import json
import os
import re
import sys

TOP_KEYS = ('Protocol', 'SessionKey', 'ServerTimeTicks', 'ServerNotification',
            'RequestId', 'AcademyDB', 'AcademyLocationDBs')
ADB_KEYS = ('AccountId', 'LastUpdate', 'ZoneVisitCharacterDBs', 'ZoneScheduleGroupRecords')
LOC_KEYS = ('AccountId', 'LocationId', 'Rank', 'Exp')

SEV_RANK = {'P0-结构': 0, 'P0-格式': 1, 'P1-语义': 2, 'P2-动态': 3, 'OK': 4}

# 这些路径的值按设计就应逐账号/逐请求不同
DYNAMIC_SCALARS = {
    'SessionKey.AccountServerId', 'SessionKey.MxToken', '<REDACTED_TOKEN>',
    'RequestId', 'AcademyDB.AccountId', 'AcademyDB.LastUpdate',
}


# ------------------------------------------------------------------ 载入
def load_inner(path):
    """抓包文件取 'inner'；普通渲染文件本身就是 inner。"""
    with io.open(path, 'r', encoding='utf-8') as fh:
        d = json.load(fh)
    if isinstance(d, dict) and 'inner' in d and isinstance(d['inner'], dict):
        return d['inner'], d
    return d, None


# ------------------------------------------------------------------ 格式化
def tname(v):
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'bool'
    if isinstance(v, int):
        return 'int'
    if isinstance(v, float):
        return 'float'
    if isinstance(v, str):
        return 'str'
    if isinstance(v, dict):
        return 'dict'
    if isinstance(v, list):
        return 'list'
    return type(v).__name__


def brief(v, width=64):
    """值的紧凑显示（带类型）。"""
    t = tname(v)
    if isinstance(v, (dict, list)):
        s = '%s(len=%d)' % (t, len(v))
        if isinstance(v, dict) and v:
            k = list(v.keys())[:3]
            s += ' keys[0:3]=%s' % (k,)
        if isinstance(v, list) and v:
            s += ' first=%s' % (tname(v[0]),)
        return s
    if isinstance(v, str):
        s = repr(v)
        if len(s) > width:
            s = s[:width - 3] + '...'
        return '%s %s' % (t, s)
    return '%s %r' % (t, v)


# ------------------------------------------------------------------ 路径级严重度
def sev_for(path, ov, mv, equal):
    if equal:
        return 'OK'
    # 结构：键缺失/多余 -> 在 walk 里直接判
    if path in DYNAMIC_SCALARS:
        return 'P2-动态'
    if path.startswith('AcademyLocationDBs[') and path.endswith('].AccountId'):
        return 'P2-动态'
    if tname(ov) != tname(mv):
        return 'P0-结构'
    return 'P1-语义'


# ------------------------------------------------------------------ 递归对比
def walk(ov, mv, path, rows):
    """把 (官方, 我们) 递归展开成行。"""
    po = path
    if isinstance(ov, dict) and isinstance(mv, dict):
        # 键序也要比：官方顺序是我们逐字节对齐的依据
        ok_order = list(ov.keys()) == list(mv.keys())
        for k in ov.keys():
            if k not in mv:
                rows.append((po + '.' + k if po else k, brief(ov[k]), '<缺失>', '否', 'P0-结构',
                             '官方有、我们没有'))
        for k in mv.keys():
            if k not in ov:
                rows.append((po + '.' + k if po else k, '<缺失>', brief(mv[k]), '否', 'P0-结构',
                             '我们有、官方没有（多余键）'))
        for k in ov.keys():
            if k in mv:
                walk(ov[k], mv[k], (po + '.' + k) if po else k, rows)
        if not ok_order and list(ov.keys()) != list(mv.keys()):
            rows.append((po or '<root>', '键序 %s' % (list(ov.keys())[:8],),
                         '键序 %s' % (list(mv.keys())[:8],), '否', 'P0-结构', '键集合/键序不同'))
        elif not ok_order:
            rows.append((po or '<root>', '键序 %d 键' % len(ov), '键序 %d 键' % len(mv),
                         '否', 'P0-结构', '键集合相同但顺序不同（逐字节对比会失败）'))
        return
    if isinstance(ov, list) and isinstance(mv, list):
        if len(ov) != len(mv):
            sev = 'P1-语义' if len(ov) > len(mv) else 'P0-结构'
            rows.append((po + '.length', 'list(len=%d)' % len(ov), 'list(len=%d)' % len(mv),
                         '否', sev, '数组长度不同'))
            # 仍然逐元素比前 min 个，暴露元素形状差异
            for i in range(min(len(ov), len(mv))):
                walk(ov[i], mv[i], '%s[%d]' % (po, i), rows)
            return
        for i in range(len(ov)):
            walk(ov[i], mv[i], '%s[%d]' % (po, i), rows)
        return
    equal = (ov == mv) and (tname(ov) == tname(mv))
    rows.append((po, brief(ov), brief(mv), '是' if equal else '否',
                 sev_for(po, ov, mv, equal), ''))


# ------------------------------------------------------------------ 单边体检（Q1-Q5）
def check_only(inner):
    out = []
    a = out.append
    sk = inner.get('SessionKey') or {}
    adb = inner.get('AcademyDB') or {}
    zv = adb.get('ZoneVisitCharacterDBs')
    locs = inner.get('AcademyLocationDBs')

    a('Q3  SessionKey.MxToken      len=%s  (期望 64)' % len(str(sk.get('MxToken') or '')))
    tok = str(sk.get('MxToken') or '')
    try:
        raw = base64.b64decode(tok, validate=True)
        a('    base64 decode          OK -> %d bytes' % len(raw))
    except Exception as e:
        a('    base64 decode          FAIL -> %s' % e)
    a('    is_uuid_guid           %s' % bool(re.fullmatch(
        r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', tok)))

    a('Q4  ServertimeTicks         %r  digits=%s  (期望 18)' % (
        inner.get('ServerTimeTicks'), len(str(inner.get('ServerTimeTicks') or ''))))

    a('Q5  AcademyDB.LastUpdate    %r' % (adb.get('LastUpdate'),))
    lu = str(adb.get('LastUpdate') or '')
    a('    ISO+ms no-tz           %s' % bool(re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3,7}', lu)))

    a('Q1  ZoneVisitCharacterDBs   type=%s len=%d' % (tname(zv), len(zv) if hasattr(zv, '__len__') else -1))
    if isinstance(zv, dict):
        dist = {}
        for v in zv.values():
            dist[len(v)] = dist.get(len(v), 0) + 1
        a('    长度分布               %s' % dict(sorted(dist.items())))
        a('    总元素                 %d' % sum(len(v) for v in zv.values()))
        empt = [k for k, v in zv.items() if len(v) == 0]
        a('    空数组 key 数          %d %s' % (len(empt), empt[:6]))
        if zv:
            ks = list(zv.keys())
            a('    键序 == 字典序         %s' % (ks == sorted(ks)))
        # 元素形状
        for k, v in zv.items():
            if v:
                a('    首个非空元素 [%s][0]    %s' % (k, json.dumps(v[0], ensure_ascii=False)[:150]))
                a('    元素类型               %s' % tname(v[0]))
                break
    elif isinstance(zv, list):
        a('    !! 是 list 不是 dict   -> 结构错误（应为 map<int_str, array>）')

    a('Q2  AcademyLocationDBs      type=%s len=%d' % (tname(locs), len(locs) if hasattr(locs, '__len__') else -1))
    if isinstance(locs, list):
        a('    LocationId             %s' % ([r.get('LocationId') for r in locs],))
        a('    Rank                   %s' % ([r.get('Rank') for r in locs],))
        a('    Exp                    %s' % ([r.get('Exp') for r in locs],))
        a('    AccountId              %s' % ([r.get('AccountId') for r in locs],))
        zero = [i for i, r in enumerate(locs) if r.get('AccountId') in (0, None)]
        if zero:
            a('    !! AccountId 为 0 的行  %s  -> 说明渲染时 aid 解成了 0' % zero)

    a('--  顶层键                    %s' % (list(inner.keys()),))
    a('    AcademyDB 键             %s' % (list(adb.keys()),))
    a('    ZoneScheduleGroupRecords %s' % brief(adb.get('ZoneScheduleGroupRecords')))
    a('    RequestId                %r  len=%s' % (inner.get('RequestId'), len(str(inner.get('RequestId') or ''))))
    a('    Protocol                 %r' % (inner.get('Protocol'),))
    a('    ServerNotification       %r' % (inner.get('ServerNotification'),))
    return out


# ------------------------------------------------------------------ 主
def main(argv=None):
    ap = argparse.ArgumentParser(description='24000 逐字段递归对比')
    ap.add_argument('--official', required=True, help='官方抓包 response.json（取 inner）')
    ap.add_argument('--ours', help='我们的 24000 inner JSON')
    ap.add_argument('--csv', help='把对比表写到这个 CSV')
    ap.add_argument('--check-only', action='store_true', help='只做官方这一侧的结构体检（Q1-Q5）')
    ap.add_argument('--label', default='', help='对比名（写进 CSV 第 0 列）')
    a = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    off, cap = load_inner(a.official)

    if a.check_only:
        for line in check_only(off):
            print(line)
        return 0

    if not a.ours:
        ap.error('--ours 必需（除非 --check-only）')
    ours, _ = load_inner(a.ours)

    rows = []
    walk(off, ours, '', rows)

    # 补齐 check 的严重度说明
    named = []
    for path, o, m, same, sev, note in rows:
        named.append([a.label, path, o, m, same, sev, note])

    named.sort(key=lambda r: (SEV_RANK.get(r[5], 9), r[1]))

    if a.csv:
        d = os.path.dirname(os.path.abspath(a.csv))
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(a.csv, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['对比', '路径', '官方值/类型', '我们的值/类型', '一致?', '严重度', '备注'])
            w.writerows(named)

    # 控制台只打非 OK 的
    cnt = {}
    for r in named:
        cnt[r[5]] = cnt.get(r[5], 0) + 1
    print('== diff %s == 行数 %d  统计 %s' % (a.label or a.official, len(named), cnt))
    for r in named:
        if r[5] == 'OK':
            continue
        print('  [%s] %s | 官方 %s | 我们 %s | %s' % (r[5], r[1], r[2], r[3], r[6]))
    print('-- OK 行数: %d' % cnt.get('OK', 0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
