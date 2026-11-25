#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end CLI test for build_noroot_apk.py --gmconfig-* (no 2 GB build).

Builds a tiny synthetic APK that carries a real-structure 5,212 B GameMainConfig,
then drives the CLI through:
  T1  --gmconfig-url  <19-char domain>   -> OK, 5212 B, self-check OK
  T2  --gmconfig-value '["http://..."]'  -> OK (short value + space padding)
  T3  --asset-replace GMC_ENTRY=PATH     -> OK (generic escape hatch)
  T4  --gmconfig-url <https 19-char>     -> must be REJECTED (budget)
  T5  --asset-replace with a 5211 B file -> must be REJECTED (structure)
  T6  --key-pem A --cert-pem B           -> must be REJECTED (pair check)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_noroot_apk as B  # noqa: E402

PY = sys.executable
SCRIPT = HERE / 'build_noroot_apk.py'
KEY = HERE / 'ba_private.key.pem'
CERT = HERE / 'ba_private.cert.pem'
LONG = 'assets/audio/voc_jp/char_10041/shirokoridingsuit_battle_tacticalaction_1.ogg'

ok = True


def check(cond, msg):
    global ok
    print('  %s %s' % ('[ok]  ' if cond else '[FAIL]', msg), flush=True)
    ok = ok and bool(cond)
    return cond


def run(args, expect_zero=True):
    r = subprocess.run([PY, str(SCRIPT)] + args, capture_output=True)
    out = (r.stdout + r.stderr).decode('utf-8', 'replace')
    good = (r.returncode == 0) == expect_zero
    return good, r.returncode, out


def make_apk(path, gmc=None):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_STORED) as z:
        z.writestr('AndroidManifest.xml', b'\x03\x00\x08\x00\x0c\x00\x00\x00')
        z.writestr(B.NSC_ENTRY, b'\x03\x00\x08\x00\x08\x01\x00\x00')
        z.writestr('resources.arsc', B.struct.pack('<HHI', 0x0002, 12, 12))
        z.writestr(B.SDKCFG_ENTRY, b'{\n "sdk_url": "https://sdk-api.yostar.cn",\n "x": 1\n}\n')
        z.writestr(B.SPARE_RAW_ENTRY, b'\x00' * 64)
        z.writestr(LONG, b'\x00' * 32)
        z.writestr(B.GMC_ENTRY, gmc if gmc is not None else B.gmconfig_synth())
        for n in B.TPINFO_ENTRIES:
            z.writestr(n, b'\x00' * 8)


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    tmp = Path(tempfile.mkdtemp(prefix='gmccli'))
    print('[*] workdir %s' % tmp)
    src = tmp / 'tiny.apk'
    make_apk(src)
    common = ['--src', str(src), '--sdk-url', 'https://sdk.example.test',
              '--key-pem', str(KEY), '--cert-pem', str(CERT),
              '--force']   # 合成包：跳过 P1-6 源包身份校验

    print('\n[T1] --gmconfig-url bapsvr-prods-cn.com (19 chars, http)')
    out1 = tmp / 't1.apk'
    good, rc, log = run(common + ['--out', str(out1),
                                  '--gmconfig-url', 'bapsvr-prods-cn.com'])
    check(good, 'CLI 退出码 %d' % rc)
    check('[2b] assets/bin/Data/e37c46fea17834108a4756797197d05a: 5212 B -> 5212 B' in log,
          '日志显示 5212 -> 5212 B')
    check('无需补空格' in log or '补 0 空格' in log, '无需补空格')
    check('其余 5 字段与源包逐字节相同：OK' in log, '构建后自检：其余 5 字段逐字节相同')
    check('结果：OK' in log, '总结果 OK')
    check('v1 结论: OK' in log, '--verify-only 内部 v1 校验 OK')
    if out1.exists():
        z = zipfile.ZipFile(out1)
        d = z.read(B.GMC_ENTRY)
        z.close()
        check(len(d) == B.GMC_SIZE, '产物里 GameMainConfig = %d B' % len(d))
        info = B.gmconfig_read(d)
        check(info['fields'][B.GMC_URL_FIELD] ==
              B.gmconfig_value_from_spec('bapsvr-prods-cn.com'),
              'ServerInfoDataUrl = %r' % info['fields'][B.GMC_URL_FIELD])

    print('\n[T2] --gmconfig-value 短值 + 空格补齐')
    out2 = tmp / 't2.apk'
    val = '["http://ba.example.test/si.json"]'
    good, rc, log = run(common + ['--out', str(out2), '--gmconfig-value', val])
    check(good, 'CLI 退出码 %d' % rc)
    check('补 1' in log or '补 ' in log, '有补齐提示')
    if out2.exists():
        z = zipfile.ZipFile(out2)
        info = B.gmconfig_read(z.read(B.GMC_ENTRY))
        z.close()
        check(info['fields'][B.GMC_URL_FIELD] == val, '回读 == %r' % val)

    print('\n[T3] --asset-replace 通用逃生口')
    patch = tmp / 'gm.bin'
    new, st = B.gmconfig_rewrite(B.gmconfig_synth(),
                                 B.gmconfig_value_from_spec('my-ba-server-cn.com', 'http'))
    patch.write_bytes(new)
    out3 = tmp / 't3.apk'
    good, rc, log = run(common + ['--out', str(out3),
                                  '--asset-replace', '%s=%s' % (B.GMC_ENTRY, patch)])
    check(good, 'CLI 退出码 %d' % rc)
    check('的结构与字段自检通过' in log, '结构与字段自检通过')
    if out3.exists():
        z = zipfile.ZipFile(out3)
        check(z.read(B.GMC_ENTRY) == new, '产物条目与本地文件逐字节相同')
        z.close()

    print('\n[T4] 拒绝：https + 19 字符域名')
    good, rc, log = run(common + ['--out', str(tmp / 't4.apk'), '--gmconfig-url',
                                  'https://state-api.bapsvr-prods-cn.com/api/state'],
                        expect_zero=False)
    check(good and rc == 1, '退出码 %d（期望 1）' % rc)
    check('放不下' in log and '值上限' in log, '给出预算说明')

    print('\n[T5] 拒绝：--asset-replace 一个 5211 B 的坏文件')
    bad = tmp / 'bad.bin'
    bad.write_bytes(new[:-1])
    good, rc, log = run(common + ['--out', str(tmp / 't5.apk'),
                                  '--asset-replace', '%s=%s' % (B.GMC_ENTRY, bad)],
                        expect_zero=False)
    check(good and rc == 1, '退出码 %d（期望 1）' % rc)
    check('必须是 5212 B' in log, '结构错误信息明确')

    print('\n[T6] 拒绝：key/cert 不配对')
    other = tmp / 'other.cert.pem'
    k2 = B.rsa_generate(1024)
    other.write_text(B.pem_wrap('CERTIFICATE', B.build_self_signed_cert(k2, cn='x')),
                     encoding='utf-8')
    good, rc, log = run(['--src', str(src), '--out', str(tmp / 't6.apk'),
                         '--key-pem', str(KEY), '--cert-pem', str(other)],
                        expect_zero=False)
    check(good and rc == 1, '退出码 %d（期望 1）' % rc)
    check('不配对' in log, '给出不配对信息')

    print('\n[T7] --gmconfig-scheme 覆盖 + URL 输入')
    good, rc, log = run(common + ['--out', str(tmp / 't7a.apk'), '--gmconfig-url',
                                  'https://state-api.bapsvr-prods-cn.com/api/state',
                                  '--gmconfig-scheme', 'http'])
    check(good and rc == 0, 'https 输入 + --gmconfig-scheme http -> 退出码 %d' % rc)
    good, rc, log = run(common + ['--out', str(tmp / 't7b.apk'),
                                  '--gmconfig-url', 'bapsvr-prod-cn.com',
                                  '--gmconfig-scheme', 'https'])
    check(good and rc == 0, '18 字符域名 + https -> 退出码 %d' % rc)
    if (tmp / 't7b.apk').exists():
        z = zipfile.ZipFile(tmp / 't7b.apk')
        info = B.gmconfig_read(z.read(B.GMC_ENTRY))
        z.close()
        check(info['fields'][B.GMC_URL_FIELD].startswith('["https://state-api.bapsvr-prod-cn.com/'),
              '值 = %r' % info['fields'][B.GMC_URL_FIELD])

    print('\n[T8] --no-v1 构建（v1 校验按需关闭）')
    good, rc, log = run(common + ['--out', str(tmp / 't8.apk'), '--no-v1',
                                  '--gmconfig-url', 'bapsvr-prods-cn.com'])
    check(good and rc == 0, '--no-v1 构建 + verify(require_v1=False) 退出码 %d' % rc)
    check('v1 结论: OK' in log, 'v1 缺失不算失败（require_v1=False）')

    print('\n[T9] --asset-replace 一般条目（非 GameMainConfig）')
    sdkf = tmp / 'sdk.json'
    payload = b'{"sdk_url": "https://other.test", "k": 2}\n'
    sdkf.write_bytes(payload)
    out9 = tmp / 't9.apk'
    good, rc, log = run(common + ['--out', str(out9),
                                  '--asset-replace', '%s=%s' % (B.SDKCFG_ENTRY, sdkf)])
    check(good and rc == 0, 'CLI 退出码 %d' % rc)
    if out9.exists():
        z = zipfile.ZipFile(out9)
        check(z.read(B.SDKCFG_ENTRY) == payload, '产物条目 == 本地文件')
        z.close()

    print('\n[T10] --verify-only 断言期望的 ServerInfoDataUrl')
    good, rc, log = run(['--verify-only', str(out1),
                         '--gmconfig-url', 'bapsvr-prods-cn.com'])
    check(good and rc == 0, '值匹配 -> 退出码 %d' % rc)
    check('ServerInfoDataUrl == 期望值: OK' in log, '打印断言结果 OK')
    good, rc, log = run(['--verify-only', str(out1),
                         '--gmconfig-url', 'other-used-domain.test'],
                        expect_zero=False)
    check(good and rc == 1, '值不匹配 -> 退出码 %d（期望 1）' % rc)

    print('\n[*] CLI e2e %s' % ('PASS' if ok else 'FAIL'))
    if ok:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print('[!] 保留 %s 供排查' % tmp)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
