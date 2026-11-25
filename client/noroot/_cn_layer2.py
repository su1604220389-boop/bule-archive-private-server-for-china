#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_cn_layer2.py -- CN 3.0.2 GameMainConfig 第二层解码器 + 字段名反搜。

第二层（国际服已验证的格式，本脚本在国服上重新做 A/B 验证）:
    key_stored   = UTF16LE(fieldName) XOR cycle8(create_key(fieldName))
    value_stored = UTF16LE(value)     XOR cycle8(create_key(fieldName))
两张表都以 base64 存进第一层 JSON。

自密钥特性 => 判定一个候选名的充要条件:
    dec_field(cand, key_ct) == UTF16LE(cand)
不需要知道别的，命中即为真。脚本据此反搜。
"""
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from CRYPTO_MT import create_key, xxhash32  # noqa: E402


def cyc8(name: str, n: int) -> bytes:
    k = create_key(name)
    return (k * (n // 8 + 2))[:n]


def dec(name: str, ct: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(ct, cyc8(name, len(ct))))


def enc(name: str, pt: bytes) -> bytes:
    return dec(name, pt)          # XOR 自逆


def u16(s: str) -> bytes:
    return s.encode('utf-16-le')


def show(b: bytes) -> str:
    try:
        s = b.decode('utf-16-le')
        if all(0x20 <= ord(c) < 0x7F for c in s):
            return repr(s)
        return 'NONASCII ' + b.hex()
    except Exception:
        return 'BAD ' + b.hex()


def b64d(s: str) -> bytes:
    return base64.b64decode(s + '=' * (-len(s) % 4))


def load(fn):
    return json.loads(Path(fn).read_text(encoding='utf-8'))


def try_name(js, cand):
    """cand 对每对键值做自密钥校验，返回命中列表 [(idx, value_bytes)]"""
    hits = []
    for i, (k_b64, v_b64) in enumerate(js.items()):
        kct = b64d(k_b64)
        if len(kct) != len(u16(cand)):
            continue
        if dec(cand, kct) == u16(cand):
            hits.append((i, dec(cand, b64d(v_b64)) if v_b64 else b''))
    return hits


def main():
    fn = sys.argv[1] if len(sys.argv) > 1 else \
        '_extract_cn/GameMainConfig_assets_bin_Data_e37c46fea17834108a4756797197d05a.json'
    js = load(fn)
    print('[*] outer JSON pairs =', len(js))
    print('[*] create_key("GameMainConfig") =', create_key('GameMainConfig').hex(' '))
    print()
    print(' idx  key_b64_chars  key_ct_bytes  =>  utf16_chars   value_ct_bytes  value_utf16_chars')
    for i, (k, v) in enumerate(js.items()):
        kb, vb = b64d(k), b64d(v)
        print('  %d   %6d        %6d          %6d          %6d           %6d'
              % (i, len(k), len(kb), len(kb) // 2, len(vb), len(vb) // 2))

    KNOWN = ['SkipTutorial', 'ToyLogin', 'Language',
             'ServerInfoDataUrl', 'DefaultConnectionGroup']
    print('\n=== 已知 5 字段名自密钥校验 ===')
    for c in KNOWN:
        h = try_name(js, c)
        print('  %-24s len=%2d  hits=%s %s'
              % (c, len(c), [i for i, _ in h],
                 [show(v) for _, v in h] if h else ''))
    print('\n=== 反搜命中的完整值（已知名）===')
    for c in KNOWN:
        for i, v in try_name(js, c):
            print('  [%d] %s = %s' % (i, c, show(v)))


if __name__ == '__main__':
    main()
