#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_cn_patch.py -- 国服 GameMainConfig 的「等长替换」实测（只写 work\\ba\\noroot\\ 下的新文件）。

做三件事：
  1. 从 APK 内存读取 assets/bin/Data/e37c46fea17834108a4756797197d05a，校验结构
     (m_Name / m_Script 长度 / 偏移)，并逐层解到明文 JSON。
  2. 用 **同长度** 的自有域名替换 ServerInfoDataUrl 里的两条 dispatcher URL
     （只换域名，URL 条数/顺序/路径保持不变 => 整串字符数不变）——方案 A。
  3. 重新加密回写，落地为 PATCHED_*.bin，并做端到端复核：
     文件大小不变、m_Name 与长度字段不变、其余 5 个字段不变、只有该 value 的密文变化。
  另附方案 B：换成更短的自有 URL，用尾部空格把 JSON 补回 545 字符。
"""
import base64
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from CRYPTO_MT import create_key, xor_with_key8  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
APK = ROOT / 'report' / '_tmp' / 'cn_base.apk'
MEMBER = 'assets/bin/Data/e37c46fea17834108a4756797197d05a'
OUTDIR = Path(__file__).resolve().parent / '_extract_cn'

# 原值（101 字符）
ORIG_VALUE = ('["https://state-api.bluearchive-cn.com/api/state",'
              '"https://stateqc-api.bluearchive-cn.com/api/state"]')
# 只换域名：bluearchive-cn.com (18) -> bapsvr-prod-cn.com (18)，长度完全一致
NEW_VALUE = ORIG_VALUE.replace('bluearchive-cn.com', 'bapsvr-prod-cn.com')

FIELD_NAMES = ('SkipTutorial', 'ServerInfoDataUrl', 'ServerName',
               'VersionCode', 'PlatformID', 'ChannelID')


def cyc8(name, n):
    k = create_key(name)
    return (k * (n // 8 + 2))[:n]


def dec(name, ct):
    return bytes(a ^ b for a, b in zip(ct, cyc8(name, len(ct))))


def b64d(s):
    return base64.b64decode(s + '=' * (-len(s) % 4))


def b64e(b):
    return base64.b64encode(b).decode()


def read_config(asset):
    """解到底，返回 {字段名: 值}（只认已破的 6 个名字）。"""
    script_len = int.from_bytes(asset[0x1014:0x1018], 'little')
    k8 = create_key('GameMainConfig')
    plain = xor_with_key8(k8, asset[0x1018:0x1018 + script_len]).decode('utf-16-le')
    js = json.loads(plain)
    out = {}
    for kb, vb in js.items():
        key_ct = b64d(kb)
        for n in FIELD_NAMES:
            if len(n) * 2 == len(key_ct) and dec(n, key_ct) == n.encode('utf-16-le'):
                out[n] = dec(n, b64d(vb)).decode('utf-16-le') if vb else ''
                break
    return out, plain, script_len, k8


def main():
    print('[1] 结构校验')
    asset = bytearray(zipfile.ZipFile(APK).read(MEMBER))
    name = bytes(asset[0x1004:0x1012]).decode()
    script_len = int.from_bytes(asset[0x1014:0x1018], 'little')
    body = bytes(asset[0x1018:0x1018 + script_len])
    print('    file_size=%d  m_Name@0x1004=%r  m_Script_len@0x1014=%d  data=0x1018..0x%X'
          % (len(asset), name, script_len, 0x1018 + script_len))
    assert name == 'GameMainConfig'
    assert 0x1018 + script_len == 5210, 0x1018 + script_len
    assert len(asset) == 5212, len(asset)
    print('    m_Script 结束 0x%X，文件 0x%X（差 %d B 对齐 padding）'
          % (0x1018 + script_len, len(asset), len(asset) - (0x1018 + script_len)))

    k8 = create_key('GameMainConfig')
    plain = xor_with_key8(k8, body).decode('utf-16-le')
    print('    layer1 chars=%d  bytes=%d' % (len(plain), len(plain) * 2))
    js = json.loads(plain)
    assert json.dumps(js, separators=(',', ':'), ensure_ascii=False) == plain, '重排布不一致'
    print('    JSON 重新序列化与原文逐字符一致: OK')

    orig, _, _, _ = read_config(asset)
    print('    原配置:', {k: (v if len(v) < 40 else v[:40] + '...') for k, v in orig.items()})
    assert orig['ServerInfoDataUrl'] == ORIG_VALUE

    print('\n[2] 构造等长新值（方案 A）')
    print('    ORIG (%d 字符) = %s' % (len(ORIG_VALUE), ORIG_VALUE))
    print('    NEW  (%d 字符) = %s' % (len(NEW_VALUE), NEW_VALUE))
    assert len(NEW_VALUE) == len(ORIG_VALUE), '长度不等，方案不成立'

    FN = 'ServerInfoDataUrl'
    old_b64_val = None
    for k, v in js.items():
        if dec(FN, b64d(k)) == FN.encode('utf-16-le'):
            old_b64_val = v
            break
    assert old_b64_val is not None and dec(FN, b64d(old_b64_val)).decode('utf-16-le') == ORIG_VALUE
    new_b64_val = b64e(dec(FN, NEW_VALUE.encode('utf-16-le')))
    print('    value b64: old %d 字符 / new %d 字符  (等长=%s)'
          % (len(old_b64_val), len(new_b64_val), len(old_b64_val) == len(new_b64_val)))
    assert len(new_b64_val) == len(old_b64_val)

    print('\n[3] 重建并回写')
    js2 = json.loads(plain)
    js2[list(js.keys())[list(js.values()).index(old_b64_val)]] = new_b64_val
    new_plain = json.dumps(js2, separators=(',', ':'), ensure_ascii=False)
    print('    layer1 chars: %d -> %d (等长=%s)' % (len(plain), len(new_plain), len(plain) == len(new_plain)))
    assert len(new_plain) == len(plain)
    new_body = xor_with_key8(k8, new_plain.encode('utf-16-le'))
    assert len(new_body) == script_len
    diff = [i for i in range(script_len) if new_body[i] != body[i]]
    print('    密文差异字节: %d 个，范围 0x%X..0x%X（均在 m_Script 内）'
          % (len(diff), min(diff), max(diff)))

    patched = bytearray(asset)
    patched[0x1018:0x1018 + script_len] = new_body
    out = OUTDIR / 'PATCHED_e37c46fea17834108a4756797197d05a.bin'
    out.write_bytes(bytes(patched))
    print('    [write] %s  (%d B)' % (out.name, len(patched)))

    print('\n[4] 端到端复核（从落盘文件重新解）')
    chk = out.read_bytes()
    assert len(chk) == len(asset), '文件大小变了'
    assert chk[:0x1018] == bytes(asset[:0x1018]), '头部/长度字段被动了'
    assert int.from_bytes(chk[0x1014:0x1018], 'little') == script_len
    got, _, _, _ = read_config(chk)
    for k in FIELD_NAMES:
        print('    %-18s = %r' % (k, got.get(k)))
    assert len(got) == 6, '有字段没认出来: %s' % got.keys()
    assert got['ServerInfoDataUrl'] == NEW_VALUE
    assert got['SkipTutorial'] == orig['SkipTutorial']
    assert got['ServerName'] == orig['ServerName']
    assert got['VersionCode'] == orig['VersionCode']
    assert got['PlatformID'] == orig['PlatformID']
    assert got['ChannelID'] == orig['ChannelID']
    print('    [OK] 替换成功，其余 5 个字段逐字段未变，文件大小与全部偏移未变')

    print('\n[5] 预算（若想放更长/更多 URL）')
    print('    m_Script 固定 %d B = %d 个 UTF-16 字符；当前 JSON 占 %d，余量 %d 字符'
          % (script_len, script_len // 2, len(plain), script_len // 2 - len(plain)))

    print('\n[6] 方案 B：换成更短的自有 URL，用尾部空格补齐到 545 字符')
    overhead = len(plain) - len(ORIG_VALUE)
    budget = script_len // 2 - overhead
    print('    固定开销(键/引号/逗号等) = %d 字符  =>  value 上限 = %d 字符' % (overhead, budget))
    SHORT = '["https://ba.example.com/si.json"]'
    assert len(SHORT) <= budget, (len(SHORT), budget)
    js4 = json.loads(plain)
    for k in js4:
        if dec(FN, b64d(k)) == FN.encode('utf-16-le'):
            js4[k] = b64e(dec(FN, SHORT.encode('utf-16-le')))
            break
    s4 = json.dumps(js4, separators=(',', ':'), ensure_ascii=False)
    print('    新 JSON = %d 字符，尾部补 %d 个空格 -> %d'
          % (len(s4), script_len // 2 - len(s4), script_len // 2))
    s4p = s4 + ' ' * (script_len // 2 - len(s4))
    assert len(s4p) == script_len // 2
    b4 = xor_with_key8(k8, s4p.encode('utf-16-le'))
    p_b = bytearray(asset)
    p_b[0x1018:0x1018 + script_len] = b4
    outb = OUTDIR / 'PATCHED_SHORT_e37c46fea17834108a4756797197d05a.bin'
    outb.write_bytes(bytes(p_b))
    print('    [write] %s  (%d B)' % (outb.name, len(p_b)))

    chk2 = outb.read_bytes()
    assert len(chk2) == len(asset)
    assert chk2[:0x1018] == bytes(asset[:0x1018])
    got2, _, _, _ = read_config(chk2)
    print('    round-trip: ServerInfoDataUrl = %r' % got2['ServerInfoDataUrl'])
    assert got2['ServerInfoDataUrl'] == SHORT
    assert len(got2) == 6
    d2 = sum(1 for i in range(script_len) if b4[i] != body[i])
    print('    [OK] 方案 B 成功：密文差 %d B，文件大小/偏移不变，其余字段不变' % d2)


if __name__ == '__main__':
    main()
