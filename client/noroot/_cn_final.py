#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_cn_final.py -- 剩余字段名反搜（用 CRYPTO_MT.create_key，带运行期自检与异常隔离）。

只打 name_len=9 与 10 的两个目标；命中判定为精确等式（自密钥 + 值可解码），
因此不可能产生假阳性。
"""
import base64
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from CRYPTO_MT import create_key  # noqa: E402

OUTER = '_extract_cn/GameMainConfig_assets_bin_Data_e37c46fea17834108a4756797197d05a.json'
REF = create_key('GameMainConfig').hex()
assert REF == '1b232806ad72c257', REF


def cyc8(k, n):
    return (k * (n // 8 + 2))[:n]


def b64d(s):
    return base64.b64decode(s + '=' * (-len(s) % 4))


W = """Server Version Ver Client App Build Patch Asset Bundle Stage Env Res Resource Game Main Sub
Local Remote Test Dev Debug Prod Live Review Tutorial Toy Login Lang Language Country Region Area
Channel Store Platform Cdn Api Host Port Url Uri State Info Data Config Setting Option Flag Mode
Type Code Name Id Idx Index Path File Dir Cache Clear Skip Show Use Enable Check Valid Device Model
Os Android Ios Cn Jp Kr Tw Global China Nexon Yostar Xd Bili Tap Start Up Down New Old Time Date
Zone Gmt Http Https Ws Wss Root Base Domain Ip Dns Proxy Gateway Entry Point Cluster Group
Connection Connect Default Current Select Target Media Audio Sound Text Table Excel Master Db
Sqlite Sql Json Xml Csv Unity Il2cpp Native Link Library Module Package Manifest Guid Hash Sign
Salt Key Token Cert Ssl Tls Header Cookie Session User Player Account Auth Logout Launch Boot Init
Stop Reload Refresh Sync Download Upload Fetch Interval Timeout Retry Count Max Min Limit Size
Length Width Height Scale Speed Ratio Prefix Suffix Svr Gid Uid Secret Locale Culture Utc Offset
Emulator Brand Jailbreak Xigncode Cheat Detect Detectable Ban Report White Black List Mask Extra
Order Rank Score Level Quest Mission Stage Story Scenario Script Dialog Voice Movie MovieSub
UrlRoot RootUrl BaseUrl HostName ServerName ClientVer AppVer AppId AppKey AppSecret Idfa
Advertising Tracking Analytics Report Event Log Logger Console Print PrintLog UploadLog""".split()

PRE = ['Is', 'Use', 'Enable', 'Has', 'Can', 'Skip', 'Show', 'Force', 'Default', 'Get', 'Set', 'Need',
       'Allow', 'Check', 'Ignore', 'Override', 'No', 'Not', 'With', 'Without', 'Auto', 'Custom',
       'Local', 'Remote', 'Server', 'Client', 'Test', 'Dev', 'Debug', 'Prod', 'Total', 'Main', 'Sub']
SUF = ['On', 'Off', 'Id', 'Ids', 'Idx', 'Type', 'Mode', 'Url', 'Data', 'Group', 'Code', 'Index',
       'Value', 'Enable', 'Enabled', 'Flag', 'Name', 'Path', 'Info', 'Version', 'Ver', 'Build',
       'Cache', 'State', 'Size', 'Count', 'Time', 'List', 'Map', 'Key', 'Root', 'Svr', 'Gid', 'Uid']


def build():
    s = set()
    for n in W:
        s.add(n)
    for a in W:
        for p in PRE:
            s.add(p + a)
        for q in SUF:
            s.add(a + q)
    for a, b in itertools.product(W, repeat=2):
        s.add(a + b)
    for a in W:
        for p in PRE:
            for q in SUF:
                s.add(p + a + q)
    return s


def main():
    js = json.loads(Path(OUTER).read_text(encoding='utf-8'))
    tg = {}
    for i, (k, v) in enumerate(js.items()):
        kct = b64d(k)
        tg.setdefault(len(kct) // 2, []).append((i, kct, b64d(v)))

    cands = build()
    print('[*] 候选池 =', len(cands))
    todo = {9: [c for c in cands if len(c) == 9],
            10: [c for c in cands if len(c) == 10]}
    print('[*] len9 = %d  len10 = %d' % (len(todo[9]), len(todo[10])))

    hits = {}
    errors = 0
    n = 0
    for L in sorted(todo):
        items = tg.get(L, [])
        if not items:
            continue
        print('--- name_len=%d (%d 个目标: %s)' % (L, len(items), [t[0] for t in items]))
        for c in todo[L]:
            n += 1
            if n % 5000 == 0:
                if create_key('GameMainConfig').hex() != REF:
                    print('!! 运行期自检失败 @ n=%d，中止' % n)
                    return
                print('    ... n=%d errors=%d' % (n, errors))
            try:
                k = create_key(c)
            except Exception:
                errors += 1
                continue
            u = c.encode('utf-16-le')
            for i, kct, vct in items:
                if bytes(a ^ b for a, b in zip(kct, cyc8(k, len(kct)))) != u:
                    continue
                val = bytes(a ^ b for a, b in zip(vct, cyc8(k, len(vct)))).decode('utf-16-le') if vct else ''
                print('    HIT idx=%d %r = %r' % (i, c, val))
                hits[c] = (i, val)
    print('\n[*] 共测试 %d 个候选，异常 %d 次' % (n, errors))
    print('[*] 命中:', {c: v for c, v in hits.items()})

    # 合并已知结果
    cfg = {}
    p = Path('_extract_cn/CN_GameMainConfig_plain.json')
    if p.exists():
        cfg = json.loads(p.read_text(encoding='utf-8'))
    for c, (i, v) in hits.items():
        cfg[c] = v
    print('\n=== 当前已还原 ===')
    for k, v in cfg.items():
        print('  %-24s = %r' % (k, v))


if __name__ == '__main__':
    main()
