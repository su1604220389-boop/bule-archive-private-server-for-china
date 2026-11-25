#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_cn_words.py -- 语义词表反搜 GameMainConfig 第二层字段名（长度匹配 + 自密钥判定）。"""
import base64
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from CRYPTO_MT import create_key, xxhash32  # noqa: E402

OUTER = '_extract_cn/GameMainConfig_assets_bin_Data_e37c46fea17834108a4756797197d05a.json'
M = 0xFFFFFFFF


def mt_key(name):
    s = xxhash32(name.encode())
    mt = [0] * 624
    mt[0] = s
    for i in range(1, 624):
        mt[i] = (1812433253 * (mt[i - 1] ^ (mt[i - 1] >> 30)) + i) & M
    for i in range(624):
        y = (mt[i] & 0x80000000) | (mt[(i + 1) % 624] & 0x7FFFFFFF)
        v = mt[(i + 397) % 624] ^ (y >> 1)
        if y & 1:
            v ^= 2567483615
        mt[i] = v & M
    out = bytearray()
    for j in range(2):
        y = mt[j]
        y ^= y >> 11
        y ^= (y << 7) & 2636928640
        y ^= (y << 15) & 4022730752
        y ^= y >> 18
        n = (y & M) >> 1
        out += bytes(((n >> (8 * k)) & 0xFF) for k in range(4))
    return bytes(out)


def cyc8(k, n):
    return (k * (n // 8 + 2))[:n]


def b64d(s):
    return base64.b64decode(s + '=' * (-len(s) % 4))


NOUN = """Server Version Ver Client App Build Patch Asset Bundle Stage Env Res Resource Game Main Sub
Local Remote Test Dev Debug Prod Live Review Tutorial Toy Login Lang Language Country Region Area
Channel Store Platform Cdn Api Host Port Url Uri State Info Data Config Setting Option Flag Mode
Type Code Name Id Idx Index Path File Dir Cache Clear Skip Show Use Enable Check Valid Device Model
Os Android Ios Cn Jp Kr Tw Global China Nexon Yostar Xd Bili Bilibili Tap Start Up Down New Old
Time Date Zone Gmt Http Https Ws Wss Root Base Sub Domain Ip Dns Proxy Gateway Entry Point Cluster
Group Connection Connect Default Current Select Target Asset Media Audio Sound Text Table Excel
Master Db Sqlite Sql Json Xml Csv Unity Il2cpp Native Link Library Module Package Manifest
Guid Hash Sign Salt Key Token Cert Ssl Tls Http2 Header Cookie Session User Player Account
Auth Loginout Logout Launch Boot Init Start Stop Reload Refresh Sync Download Upload Fetch
Interval Timeout Retry Count Max Min Limit Size Length Width Height Scale Speed Ratio""".split()
PRE = ['Is', 'Use', 'Enable', 'Has', 'Can', 'Skip', 'Show', 'Force', 'Default', 'Get', 'Set',
       'Need', 'Allow', 'Check', 'Ignore', 'Override', 'No', 'Not', 'With', 'Without', 'Auto',
       'Custom', 'Local', 'Remote', 'Server', 'Client', 'Test', 'Dev', 'Debug', 'Prod', 'Total']
SUF = ['On', 'Off', 'Id', 'Ids', 'Idx', 'Type', 'Mode', 'Url', 'Data', 'Group', 'Code', 'Index',
       'Value', 'Enable', 'Enabled', 'Flag', 'Name', 'Path', 'Info', 'Version', 'Ver', 'Build',
       'Cache', 'State', 'Size', 'Count', 'Time', 'UrlS', 'List', 'Map', 'Key', 'Salt']


def gen():
    s = set()
    for n in NOUN:
        s.add(n)
        for p in PRE:
            s.add(p + n)
        for q in SUF:
            s.add(n + q)
    print('  stage-1 words =', len(s))
    # 两词 PascalCase
    for a, b in itertools.product(NOUN, repeat=2):
        s.add(a + b)
    print('  stage-2 (两词) =', len(s))
    # 三词：pre + noun + suf（只在长度 9~12 时有意义）
    for a, b, c in itertools.product(PRE, NOUN[:40], SUF[:20]):
        s.add(a + b + c)
    print('  stage-3 (三词) =', len(s))
    return s


def main():
    js = json.loads(Path(OUTER).read_text(encoding='utf-8'))
    tg = {}
    for i, (k, v) in enumerate(js.items()):
        kct = b64d(k)
        tg.setdefault(len(kct) // 2, []).append((i, kct, b64d(v)))
    print('[*] targets by name_len:', {L: [t[0] for t in v] for L, v in sorted(tg.items())})

    cands = gen()
    print('[*] 候选总数 =', len(cands))
    print('[*] 按长度:', {L: sum(1 for c in cands if len(c) == L) for L in sorted(tg)})

    cfg = {}
    for L, items in sorted(tg.items()):
        print('\n--- name_len=%d' % L)
        for c in cands:
            if len(c) != L:
                continue
            k = mt_key(c)
            u = c.encode('utf-16-le')
            for i, kct, vct in items:
                if bytes(a ^ b for a, b in zip(kct, cyc8(k, len(kct)))) != u:
                    continue
                val = bytes(a ^ b for a, b in zip(vct, cyc8(k, len(vct)))).decode('utf-16-le') if vct else ''
                print('    HIT idx=%d %r = %r' % (i, c, val))
                cfg[c] = val

    print('\n=== 已还原字段 ===')
    for k, v in cfg.items():
        print('  %-24s = %r' % (k, v))
    Path('_extract_cn/CN_GameMainConfig_plain.json').write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    print('[write] _extract_cn/CN_GameMainConfig_plain.json')


if __name__ == '__main__':
    main()
