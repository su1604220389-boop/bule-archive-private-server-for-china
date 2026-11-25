#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_cn_one.py -- 分片反搜 + 心跳自检。

用法:
    python _cn_one.py sanity               # 30000 次 create_key 心跳
    python _cn_one.py slice L a b          # 测长度 L 候选的第 [a,b) 片
"""
import base64
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from CRYPTO_MT import create_key  # noqa: E402

OUTER = '_extract_cn/GameMainConfig_assets_bin_Data_e37c46fea17834108a4756797197d05a.json'
REF = '1b232806ad72c257'
HITS = '_extract_cn/hits.jsonl'

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
Order Rank Score Level Quest Mission Story Scenario Script Dialog Voice Movie UrlRoot RootUrl
BaseUrl HostName ServerName ClientVer AppVer AppId AppKey SecretKey Idfa Advertising Tracking
Analytics Event Logger Console PrintLog UploadLog AssetVer ResVer""".split()

PRE = ['Is', 'Use', 'Enable', 'Has', 'Can', 'Skip', 'Show', 'Force', 'Default', 'Get', 'Set', 'Need',
       'Allow', 'Check', 'Ignore', 'Override', 'No', 'Not', 'With', 'Auto', 'Custom', 'Local',
       'Remote', 'Server', 'Client', 'Test', 'Dev', 'Debug', 'Prod', 'Total', 'Main', 'Sub']
SUF = ['On', 'Off', 'Id', 'Ids', 'Idx', 'Type', 'Mode', 'Url', 'Data', 'Group', 'Code', 'Index',
       'Value', 'Enable', 'Enabled', 'Flag', 'Name', 'Path', 'Info', 'Version', 'Ver', 'Build',
       'Cache', 'State', 'Size', 'Count', 'Time', 'List', 'Map', 'Key', 'Root', 'Svr', 'Gid', 'Uid']


def build():
    s = set(W)
    for a in W:
        for p in PRE:
            s.add(p + a)
        for q in SUF:
            s.add(a + q)
    for a, b in itertools.product(W, repeat=2):
        s.add(a + b)
    return sorted(s)


def cyc8(k, n):
    return (k * (n // 8 + 2))[:n]


def b64d(s):
    return base64.b64decode(s + '=' * (-len(s) % 4))


def targets():
    js = json.loads(Path(OUTER).read_text(encoding='utf-8'))
    tg = {}
    for i, (k, v) in enumerate(js.items()):
        kct = b64d(k)
        tg.setdefault(len(kct) // 2, []).append((i, kct, b64d(v)))
    return tg


def sanity():
    names = build()
    print('pool', len(names), flush=True)
    for n in range(30000):
        c = names[n % len(names)]
        k = create_key(c)
        if n % 3000 == 0:
            ok = create_key('GameMainConfig').hex() == REF
            print('  n=%d  key(%r)=%s  selfcheck=%s' % (n, c, k.hex(), ok), flush=True)
            if not ok:
                print('SELFCHECK FAIL', flush=True)
                return
    print('sanity OK', flush=True)


def slice_(L, a, b):
    tg = targets()
    items = tg.get(L, [])
    names = [c for c in build() if len(c) == L]
    part = names[a:b]
    print('L=%d total=%d slice=[%d,%d) n=%d targets=%s'
          % (L, len(names), a, b, len(part), [t[0] for t in items]), flush=True)
    n = 0
    hit = 0
    for c in part:
        n += 1
        k = create_key(c)
        u = c.encode('utf-16-le')
        for i, kct, vct in items:
            if bytes(x ^ y for x, y in zip(kct, cyc8(k, len(kct)))) != u:
                continue
            val = bytes(x ^ y for x, y in zip(vct, cyc8(k, len(vct)))).decode('utf-16-le') if vct else ''
            print('  HIT idx=%d %r = %r' % (i, c, val), flush=True)
            with open(HITS, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'idx': i, 'name': c, 'value': val}, ensure_ascii=False) + '\n')
            hit += 1
    print('DONE n=%d hits=%d' % (n, hit), flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'sanity':
        sanity()
    else:
        slice_(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
