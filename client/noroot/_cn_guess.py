#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_cn_guess.py -- 用独立实现的 MT19937 校验 + 语义候选词表反搜 4 个未知字段名。

同时对照 CRYPTO_MT.create_key（作为算法真值），确认独立实现一致。
"""
import base64
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from CRYPTO_MT import create_key as ref_create_key  # noqa: E402
from CRYPTO_MT import xxhash32                      # noqa: E402

M = 0xFFFFFFFF
OUTER = '_extract_cn/GameMainConfig_assets_bin_Data_e37c46fea17834108a4756797197d05a.json'


def mt19937_key(name: str) -> bytes:
    """独立实现：MT19937(s=xxhash32(name)) -> 8 字节，Next()=(genrand>>1)&0x7FFFFFFF。"""
    s = xxhash32(name.encode())
    mt = [0] * 624
    mt[0] = s
    for i in range(1, 624):
        mt[i] = (1812433253 * (mt[i - 1] ^ (mt[i - 1] >> 30)) + i) & M
    out = []
    idx = 624
    state = mt
    for _ in range(2):                      # 两次 Next() = 8 字节
        if idx >= 624:
            for i in range(624):
                y = (state[i] & 0x80000000) | (state[(i + 1) % 624] & 0x7FFFFFFF)
                v = state[(i + 397) % 624] ^ (y >> 1)
                if y & 1:
                    v ^= 2567483615
                state[i] = v & M
            idx = 0
        y = state[idx]
        idx += 1
        y ^= y >> 11
        y ^= (y << 7) & 2636928640
        y ^= (y << 15) & 4022730752
        y ^= y >> 18
        n = (y & M) >> 1
        out += [(n >> (8 * k)) & 0xFF for k in range(4)]
    return bytes(out)


def b64d(s):
    return base64.b64decode(s + '=' * (-len(s) % 4))


def cyc8_k(k, n):
    return (k * (n // 8 + 2))[:n]


def check(name, key_ct):
    k = mt19937_key(name)
    u = name.encode('utf-16-le')
    if len(u) != len(key_ct):
        return None
    if bytes(a ^ b for a, b in zip(key_ct, cyc8_k(k, len(key_ct)))) == u:
        return k
    return None


def main():
    # sanity: 独立实现 vs CRYPTO_MT
    for nm in ('GameMainConfig', 'Excel.zip', 'SkipTutorial', 'ServerInfoDataUrl'):
        a, b = mt19937_key(nm), ref_create_key(nm)
        print('[sanity] %-20s mine=%s ref=%s %s' % (nm, a.hex(), b.hex(), 'OK' if a == b else 'MISMATCH'))
    print()

    js = json.loads(Path(OUTER).read_text(encoding='utf-8'))
    tg = [(i, b64d(k), b64d(v)) for i, (k, v) in enumerate(js.items())]

    CURATED = ['SkipTutorial', 'ToyLogin', 'Language', 'ServerInfoDataUrl', 'DefaultConnectionGroup',
               'ReviewMode', 'IsReviewMode', 'LanguageCode', 'CountryCode', 'UseToyLogin',
               'ToyLoginType', 'EnableToyLogin', 'SkipToyLogin', 'LanguageId', 'LanguageType',
               'LanguageIndex', 'ServerInfoData', 'ServerInfoUrl', 'ServerInfo', 'StateUrl',
               'StateApiUrl', 'ApiUrl', 'ConnectionGroup', 'DefaultGroup', 'DefaultConnect',
               'DefaultConnection', 'IsChinaBuild', 'IsChinaVersion', 'ChinaVersion', 'LocalVersion',
               'StoreType', 'PlatformType', 'ChannelType', 'CountryType', 'RegionCode', 'AreaCode',
               'UseReviewMode', 'ShowReviewMode', 'IsDebugBuild', 'IsDevBuild', 'IsTestBuild',
               'EnableTutorial', 'SkipAllTutorial', 'ShowSkipTutorial',
               'ServerInfoDataUrlCN', 'ToyLoginOn', 'ToyLoginEnable', 'UseToyLoginFlag']

    print('=== 人工候选词表 (%d) ===' % len(CURATED))
    hit = 0
    for c in CURATED:
        for i, kct, vct in tg:
            if len(kct) != len(c) * 2:
                continue
            k = check(c, kct)
            if k:
                val = bytes(a ^ b for a, b in zip(vct, cyc8_k(k, len(vct)))).decode('utf-16-le') if vct else ''
                print('  HIT idx=%d %r = %r  (k=%s)' % (i, c, val, k.hex()))
                hit += 1
    print('  hits =', hit)

    # 生成式：prefix/suffix 组合
    PRE = ['Is', 'Use', 'Enable', 'Has', 'Can', 'Skip', 'Show', 'Force', 'Default', 'Get', 'Set',
           'Need', 'Allow', 'Check', 'Ignore', 'Override', 'Local', 'Remote', 'Server', 'Client',
           'Test', 'Dev', 'Debug', 'Release', 'Prod', 'Main', 'Sub', 'Extra', 'Old', 'New', 'No']
    SUF = ['On', 'Off', 'Id', 'Ids', 'Idx', 'Type', 'Mode', 'Url', 'UrlS', 'Data', 'Group', 'Code',
           'Index', 'Value', 'Enable', 'Enabled', 'Flag', 'Name', 'Path', 'Info', 'Version', 'Build',
           'Tutorial', 'Login', 'Language', 'Lang', 'Server', 'Api', 'Host', 'Cache', 'State', 'Scene',
           'ModeType', 'ModeId', 'GroupId']
    BASE = ['ToyLogin', 'Language', 'SkipTutorial', 'ServerInfoDataUrl', 'DefaultConnectionGroup',
            'ReviewMode', 'Tutorial', 'Login', 'Server', 'Info', 'Data', 'Url', 'State', 'Group',
            'Connection', 'Config', 'Country', 'Region', 'Channel', 'Platform', 'Store', 'Env',
            'Environment', 'Version', 'Build', 'Test', 'Debug', 'App', 'Game', 'Main', 'China', 'Cn']
    gen = set()
    for b in BASE:
        gen.add(b)
        for p in PRE:
            gen.add(p + b)
            gen.add(p + b[0].lower() + b[1:] if b[:1].isupper() else b)
        for s in SUF:
            gen.add(b + s)
        for p in PRE[:12]:
            for s in SUF[:12]:
                gen.add(p + b + s)
    print('\n=== 生成式候选 (%d) ===' % len(gen))
    hit2 = 0
    for c in gen:
        if not (1 <= len(c) <= 40):
            continue
        for i, kct, vct in tg:
            if len(kct) != len(c) * 2:
                continue
            k = check(c, kct)
            if k:
                val = bytes(a ^ b for a, b in zip(vct, cyc8_k(k, len(vct)))).decode('utf-16-le') if vct else ''
                print('  HIT idx=%d %r = %r' % (i, c, val))
                hit2 += 1
    print('  hits =', hit2)


if __name__ == '__main__':
    main()
