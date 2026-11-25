#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_cn_verify.py -- 国服 3.0.2 GameMainConfig 最终校验：6/6 字段闭合 + 落盘。

每个字段都必须满足自密钥判定式 dec(name, key_ct) == UTF16LE(name)；
并断言 6 个键全部被已知字段名认领（没有剩余未知键）。
"""
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from CRYPTO_MT import create_key, xor_with_key8  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
APK = ROOT / 'report' / '_tmp' / 'cn_base.apk'
MEMBER = 'assets/bin/Data/e37c46fea17834108a4756797197d05a'
OUTDIR = Path(__file__).resolve().parent / '_extract_cn'

NAMES = ['SkipTutorial', 'ServerInfoDataUrl', 'ServerName',
         'VersionCode', 'PlatformID', 'ChannelID']


def cyc8(name, n):
    k = create_key(name)
    return (k * (n // 8 + 2))[:n]


def dec(name, ct):
    return bytes(a ^ b for a, b in zip(ct, cyc8(name, len(ct))))


def b64d(s):
    return base64.b64decode(s + '=' * (-len(s) % 4))


def main():
    import zipfile
    asset = zipfile.ZipFile(APK).read(MEMBER)
    script_len = int.from_bytes(asset[0x1014:0x1018], 'little')
    k8 = create_key('GameMainConfig')
    plain = xor_with_key8(k8, asset[0x1018:0x1018 + script_len]).decode('utf-16-le')
    js = json.loads(plain)
    print('[*] 外层 6 对；layer1 = %d 字符 / %d B' % (len(plain), script_len))

    cfg = {}
    claimed = set()
    for idx, (kb, vb) in enumerate(js.items()):
        key_ct, val_ct = b64d(kb), b64d(vb)
        hit = None
        for n in NAMES:
            if len(n) * 2 == len(key_ct) and dec(n, key_ct) == n.encode('utf-16-le'):
                hit = n
                break
        if not hit:
            print('  !! idx %d 未被认领（name_len=%d）' % (idx, len(key_ct) // 2))
            continue
        claimed.add(hit)
        v = dec(hit, val_ct).decode('utf-16-le') if val_ct else ''
        cfg[hit] = v
        print('  [%d] %-18s (name_len=%2d, val=%3d 字符) = %r' % (idx, hit, len(hit), len(v), v))

    missing = [n for n in NAMES if n not in claimed]
    print('\n[*] 闭合性: 已认领 %d / 6，缺失 %s' % (len(claimed), missing or '无'))
    assert not missing, missing
    assert len(claimed) == len(js), '有未被认领的键'

    OUTDIR.mkdir(exist_ok=True)
    out = OUTDIR / 'CN_GameMainConfig_plain.json'
    out.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    print('[write] %s' % out)
    print('\n=== 国服 3.0.2 GameMainConfig（6/6 完整）===')
    for k, v in cfg.items():
        print('  %-18s = %r' % (k, v))


if __name__ == '__main__':
    main()
