#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SIGNER_FIXES 的独立证据测试台（不生成 2 GB 包，全部用微型 APK / 内存对象）。

用法：
  python _signfix_test.py                       # 测当前 build_noroot_apk.py
  python _signfix_test.py --module build_noroot_apk.py.orig   # 测"改前"版本
  python _signfix_test.py --live BA_noroot_v1.apk            # 额外跑真包只读复核

设计原则：
  * 不依赖待测模块的内部 API 名称（只调 build_v1 / do_build / verify / verify_v1 这类
    两个版本都有的入口），这样 .orig 与新版本可以用同一份脚本对比。
  * 校验器自己重写：严格 ManifestParser（≤72 B、续行必须以 1 个空格开头）、
    apksig 风格的宽松 ManifestParser、独立的 v3 minSdk 读取、独立的 AXML 写入器。
"""
import argparse
import base64
import hashlib
import importlib.util
import os
import shutil
import struct
import sys
import tempfile
import traceback
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

RESULTS = []          # (id, title, status, detail)


def report(pid, title, ok, detail=''):
    RESULTS.append((pid, title, 'OK' if ok else 'FAIL', detail))
    mark = 'PASS' if ok else 'FAIL'
    print('  [%s] %-4s %-46s %s' % (pid, mark, title, detail))


def load_module(path):
    """把待测脚本复制到临时目录再 import（避免正在被并发写入时读到半截文件）。"""
    tmpdir = tempfile.mkdtemp(prefix='sigfixmod')
    dst = os.path.join(tmpdir, 'target_mod.py')
    shutil.copyfile(path, dst)
    spec = importlib.util.spec_from_file_location('target_mod', dst)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['target_mod'] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# A. 独立 AXML 写入器（不复用待测模块，避免"自己验自己"）
# ---------------------------------------------------------------------------
class MiniAxml:
    def __init__(self):
        self.items, self.idx, self.chunks, self.line = [], {}, [], 1

    def s(self, text):
        if text not in self.idx:
            self.idx[text] = len(self.items)
            self.items.append(text)
        return self.idx[text]

    def pool(self):
        body = bytearray()
        offs = []
        for it in self.items:
            offs.append(len(body))
            b = it.encode('utf-8')
            n16 = len(it.encode('utf-16-le')) // 2
            for n in (n16, len(b)):
                if n > 0x7F:
                    body += bytes([0x80 | ((n >> 8) & 0x7F), n & 0xFF])
                else:
                    body += bytes([n])
            body += b + b'\x00'
        head = 28 + 4 * len(self.items)
        body += b'\x00' * ((-(head + len(body))) % 4)
        return (struct.pack('<HHIIIIII', 1, 28, head + len(body), len(self.items),
                            0, 0x100, head, 0)
                + b''.join(struct.pack('<I', o) for o in offs) + bytes(body))

    def start(self, tag, attrs=()):
        ti = self.s(tag)
        ab = b''
        for (nm, dt, data, raw) in attrs:
            ab += struct.pack('<IIIHBBI', 0xFFFFFFFF, self.s(nm), raw, 8, 0, dt, data)
        self.chunks.append(struct.pack('<HHIIIIIHHHHHH', 0x0102, 16,
                                       36 + 20 * len(attrs), self.line,
                                       0xFFFFFFFF, 0xFFFFFFFF, ti, 20, 20,
                                       len(attrs), 0, 0, 0) + ab)
        self.line += 1

    def end(self, tag):
        self.chunks.append(struct.pack('<HHIIIII', 0x0103, 16, 24, self.line,
                                       0xFFFFFFFF, 0xFFFFFFFF, self.s(tag)))
        self.line += 1

    def build(self):
        body = (self.pool() + struct.pack('<HHI', 0x0180, 8, 8)
                + b''.join(self.chunks))
        return struct.pack('<HHI', 3, 8, 8 + len(body)) + body


def make_manifest(pkg='com.RoamingStar.BlueArchive', vc=73, vn='3.0.2',
                  min_sdk=24, target_sdk=33, nsc=0x7F120001):
    a = MiniAxml()
    a.start('manifest', [('package', 0x03, a.s(pkg), a.s(pkg)),
                         ('versionCode', 0x10, vc, 0xFFFFFFFF),
                         ('versionName', 0x03, a.s(vn), a.s(vn))])
    a.start('uses-sdk', [('minSdkVersion', 0x10, min_sdk, 0xFFFFFFFF),
                         ('targetSdkVersion', 0x10, target_sdk, 0xFFFFFFFF)])
    a.end('uses-sdk')
    a.start('application', [('networkSecurityConfig', 0x01, nsc, 0xFFFFFFFF),
                            ('extractNativeLibs', 0x12, 0xFFFFFFFF, 0xFFFFFFFF)])
    a.end('application')
    a.end('manifest')
    return a.build()


# ---------------------------------------------------------------------------
# B. 两个独立 ManifestParser（严格 / 宽松）
# ---------------------------------------------------------------------------
def parse_manifest_strict(data):
    """严格按 JAR 规范：每行 ≤72 B；续行必须以单个空格开头；属性必须 'key: value'。

    返回 (main, sections, violations)。violations 非空即不合规。
    """
    viol = []
    if data and not data.endswith(b'\r\n'):
        viol.append('文件未以 CRLF 结束')
    lines = data.split(b'\r\n')
    if lines and lines[-1] == b'':
        lines = lines[:-1]
    for i, ln in enumerate(lines):
        if len(ln) > 72:
            viol.append('第 %d 行 %d B > 72' % (i + 1, len(ln)))
        if len(ln) == 0:
            continue
        if ln.startswith(b'\x00'):
            viol.append('第 %d 行含 NUL' % (i + 1))
    main, sections, cur, last = {}, [], {}, None
    seen_blank = False
    for ln in lines:
        if ln == b'':
            if cur:
                if seen_blank:
                    sections.append(cur)
                else:
                    main, seen_blank = cur, True
                cur = {}
            last = None
            continue
        if ln.startswith(b' '):
            if last is None:
                viol.append('续行没有可续的属性: %r' % ln[:40])
                continue
            cur[last] += ln[1:]
            continue
        k, sep, v = ln.partition(b': ')
        if not sep:
            viol.append('非法属性行: %r' % ln[:60])
            continue
        cur[k] = v
        last = k
    if cur:
        (sections if seen_blank else []).append(cur)
        if not seen_blank:
            main = cur
    dec = lambda d: {k.decode('utf-8'): v.decode('utf-8') for k, v in d.items()}
    return dec(main), [(dec(s).get('Name'), dec(s)) for s in sections], viol


def parse_manifest_liberal(data):
    """模仿 apksig ManifestParser / java.util.jar.Manifest 的宽松读法：
    接受 CRLF / LF / CR 结尾，续行拼接，不做行长限制。"""
    text = data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    main, sections, cur, last = {}, [], {}, None
    seen = False
    for ln in text.split(b'\n'):
        if ln == b'':
            if cur:
                if seen:
                    sections.append(cur)
                else:
                    main, seen = cur, True
                cur = {}
            last = None
            continue
        if ln.startswith(b' '):
            if last is not None:
                cur[last] += ln[1:]
            continue
        k, sep, v = ln.partition(b':')
        if not sep:
            continue
        cur[k] = v[1:] if v.startswith(b' ') else v
        last = k
    if cur:
        if seen:
            sections.append(cur)
        else:
            main = cur
    dec = lambda d: {k.decode('utf-8', 'replace'): v.decode('utf-8', 'replace')
                     for k, v in d.items()}
    return dec(main), [(dec(s).get('Name'), dec(s)) for s in sections]


# ---------------------------------------------------------------------------
# C. 独立的 APK 签名块读取（只读，用来取 v3 minSdk / v2 证书）
# ---------------------------------------------------------------------------
def _lp(b, i):
    n = struct.unpack('<I', b[i:i + 4])[0]
    return b[i + 4:i + 4 + n], i + 4 + n


def read_block(path):
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        f.seek(max(0, size - 70000))
        tail = f.read()
        i = tail.rfind(b'PK\x05\x06')
        _s, _a, _b, _n1, _n2, cdsize, cdoff, _c = struct.unpack('<IHHHHIIH',
                                                                tail[i:i + 22])
        if cdoff < 32:
            return {}
        f.seek(cdoff - 24)
        t = f.read(24)
        if t[8:] != b'APK Sig Block 42':
            return {}
        bsz = struct.unpack('<Q', t[:8])[0]
        bs = cdoff - bsz - 8
        f.seek(bs + 8)
        body = f.read(bsz - 24)
    out, p = {}, 0
    while p < len(body):
        pl = struct.unpack('<Q', body[p:p + 8])[0]
        pid = struct.unpack('<I', body[p + 8:p + 12])[0]
        out[pid] = body[p + 12:p + 8 + pl]
        p += 8 + pl
    return out


def v3_minsdk(path):
    v3 = read_block(path).get(0xF05368C0)
    if not v3:
        return None
    signers, _ = _lp(v3, 0)
    signer, _ = _lp(signers, 0)
    sd, p = _lp(signer, 0)
    _ds, q = _lp(sd, 0)
    _cs, q = _lp(sd, q)
    return struct.unpack('<II', sd[q:q + 8])


def v2_cert_and_pub(path):
    v2 = read_block(path).get(0x7109871A)
    if not v2:
        return None, None
    signers, _ = _lp(v2, 0)
    signer, _ = _lp(signers, 0)
    sd, p = _lp(signer, 0)
    _sigs, p = _lp(signer, p)
    pub, p = _lp(signer, p)
    _ds, q = _lp(sd, 0)
    certs, q = _lp(sd, q)
    one, _ = _lp(certs, 0)
    return one, pub


def cert_spki_of(cert_der):
    """独立解析证书的 subjectPublicKeyInfo DER（用于和 v2 块里的 pub 对比）。"""
    tag = cert_der[0]
    i = 1
    if cert_der[i] & 0x80:
        n = cert_der[i] & 0x7F
        i += 1 + n
    else:
        i += 1
    vo = i                                  # tbsCertificate 内容起点
    tag2 = cert_der[vo]
    j = vo + 1
    if cert_der[j] & 0x80:
        n = cert_der[j] & 0x7F
        j += 1 + n
    else:
        j += 1
    tbs_val = j                             # tbs 内容起点
    pos = tbs_val
    kids = []
    while pos < len(cert_der):
        st = pos
        tag3 = cert_der[st]
        k = st + 1
        if cert_der[k] & 0x80:
            n = cert_der[k] & 0x7F
            ln = int.from_bytes(cert_der[k + 1:k + 1 + n], 'big')
            k += 1 + n
        else:
            ln = cert_der[k]
            k += 1
        kids.append((tag3, k, k + ln, st))
        pos = k + ln
        if tag3 == 0x03 and len(kids) > 1:
            pass
    idx = 1 if kids[0][0] == 0xA0 else 0
    spki = kids[idx + 5]
    return bytes(cert_der[spki[3]:spki[2]])


# ---------------------------------------------------------------------------
# D. 微型 APK
# ---------------------------------------------------------------------------
LONGNAME = 'assets/audio/voc_jp/jp_shirokoridingsuit/shirokoridingsuit_' \
           'battle_tacticalaction_1_long_long_long_name.ogg'


def make_tiny(path, arsc_method=0, **man):
    man_bin = make_manifest(**man)
    arsc = b'\x02\x00\x0c\x00' + b'ARSC' * 8
    sdkcfg = b'{\n "sdk_url": "https://sdk-api.yostar.cn",\n "x": 1\n}\n'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_STORED) as z:
        z.writestr('AndroidManifest.xml', man_bin)
        z.writestr('res/Dk.xml', b'\x03\x00\x08\x00\x08\x01\x00\x00')
        if arsc_method == 8:
            zi = zipfile.ZipInfo('resources.arsc', (2026, 11, 16, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, arsc)
        else:
            z.writestr('resources.arsc', arsc)
        z.writestr('assets/SDKConfigSettings.json', sdkcfg)
        z.writestr('res/E5.ogg', b'\x00' * 64)
        z.writestr(LONGNAME, b'x' * 40)
        for n in ('assets/__tpinfo.tp', 'assets/__tpinfo.tsc',
                  'assets/__tpinfo.tsc.sig', 'assets/__tpinfo.tsd',
                  'assets/__tpinfo.tsd.sig'):
            z.writestr(n, b'\x00' * 8)
        z.writestr('META-INF/BACN.SF', b'old sf')
        z.writestr('META-INF/BACN.RSA', b'old rsa')
        z.writestr('META-INF/MANIFEST.MF', b'Manifest-Version: 1.0\r\n\r\n')
    return path


def mod_has(mod, name):
    return hasattr(mod, name) and callable(getattr(mod, name))


def build_tiny(mod, tmp, key, cert, name='out.apk', **kw):
    src = make_tiny(os.path.join(tmp, 'tiny_%s' % name))
    out = os.path.join(tmp, name)
    kw.setdefault('v1_on', True)
    mod.do_build(src, out, None, None, 'user', key, cert, **kw)
    return src, out


# ---------------------------------------------------------------------------
# E. 各项测试
# ---------------------------------------------------------------------------
def t1_sf_header(mod, tmp, key, cert):
    items = [('res/Dk.xml', hashlib.sha256(b'x').digest()),
             (LONGNAME, hashlib.sha256(b'y').digest())]
    mf, sf = mod.build_v1(items)
    main_sf, secs = parse_manifest_liberal(sf)
    has = main_sf.get('X-Android-APK-Signed')
    ok_val = (has is not None and
              sorted(p.strip() for p in has.split(',') if p.strip()) == ['2', '3'])
    # 位置：必须在主属性区（第一个空行之前），且不在任何 Name 段里
    first_blank = sf.find(b'\r\n\r\n')
    in_main = sf.find(b'X-Android-APK-Signed') < first_blank and \
        sf.find(b'X-Android-APK-Signed') > sf.find(b'SHA-256-Digest-Manifest')
    report('P1', '.SF 有 X-Android-APK-Signed 且值为 "2, 3"', ok_val and in_main,
           'value=%r, in_main_section=%s' % (has, in_main))
    return ok_val and in_main


def t2_wrap(mod, tmp, key, cert):
    long_name = 'assets/' + 'x' * 83 + '/' + 'y' * 97 + '.bin'
    uni_name = 'assets/中文目录/名字_ümlaut_日本語_' + 'z' * 70 + '.bin'
    items = [(long_name, hashlib.sha256(b'L').digest()),
             (uni_name, hashlib.sha256(b'U').digest()),
             ('resources.arsc', hashlib.sha256(b'R').digest())]
    mf, sf = mod.build_v1(items)
    main, secs, viol = parse_manifest_strict(mf)
    liber_main, liber_secs = parse_manifest_liberal(mf)
    lens = [len(x) for x in mf.split(b'\r\n')]
    names_strict = [n for n, _ in secs]
    names_liber = [n for n, _ in liber_secs]
    digests_ok = all(
        base64.b64encode(hashlib.sha256({'assets/' + 'x' * 83 + '/' + 'y' * 97 + '.bin': b'L',
                                         uni_name: b'U'}.get(n, b'')).digest()).decode()
        == d.get('SHA-256-Digest')
        for n, d in secs if n != 'resources.arsc')
    ok = (not viol and lens and max(lens) <= 72 and
          names_strict == names_liber == [long_name, uni_name, 'resources.arsc'] and
          digests_ok)
    report('P2', 'MANIFEST 每行 ≤72 B 且续行能拼回', ok,
           'max=%d over72=%d continuations=%d strict_viol=%s'
           % (max(lens), sum(1 for n in lens if n > 72),
              sum(1 for x in mf.split(b'\r\n') if x.startswith(b' ')),
              viol[:2] if viol else '无'))
    # 严格/宽松两个 parser 都必须还原出同样的条目名和摘要
    return ok


def make_fake_zip(path, mod, key, cert, entries, sf_mutator=None):
    """用模块自己的 build_v1/pkcs7 生成 v1 签名文件，写进一个真正的 zip。"""
    items = [(n, hashlib.sha256(d).digest()) for n, d in entries]
    mf, sf = mod.build_v1(items)
    if sf_mutator:
        sf = sf_mutator(sf)
    p7 = mod.pkcs7_signed_data(key, cert, sf)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_STORED) as z:
        for n, d in entries:
            z.writestr(n, d)
        z.writestr('META-INF/MANIFEST.MF', mf)
        z.writestr('META-INF/CERT.SF', sf)
        z.writestr('META-INF/CERT.RSA', p7)
    return path


def t3_verify_v1(mod, tmp, key, cert):
    if not mod_has(mod, 'verify_v1'):
        report('P3', 'verify() 校验 v1（摘要/SF/PKCS#7/头/残留）', False,
               '该版本没有 verify_v1()')
        return False
    base = make_fake_zip(os.path.join(tmp, 'v1_ok.zip'), mod, key, cert,
                         [('a.txt', b'aaa'), ('b/c.bin', b'bbb')])
    with zipfile.ZipFile(base) as z:
        good = mod.verify_v1(z)
    report('P3', 'verify() 校验 v1：正常包应通过', good, 'verify_v1()=%s' % good)

    # 负例 1：内容被篡改
    bad1 = os.path.join(tmp, 'v1_bad_content.zip')
    with zipfile.ZipFile(base) as z:
        items = [(n, z.read(n)) for n in z.namelist() if not n.startswith('META-INF/')]
        mf = z.read('META-INF/MANIFEST.MF')
        sf = z.read('META-INF/CERT.SF')
        p7 = z.read('META-INF/CERT.RSA')
    items[0] = (items[0][0], b'TAMPERED')
    with zipfile.ZipFile(bad1, 'w', zipfile.ZIP_STORED) as z:
        for n, d in items:
            z.writestr(n, d)
        z.writestr('META-INF/MANIFEST.MF', mf)
        z.writestr('META-INF/CERT.SF', sf)
        z.writestr('META-INF/CERT.RSA', p7)
    with zipfile.ZipFile(bad1) as z:
        r1 = mod.verify_v1(z)
    report('P3a', 'v1 内容被篡改 -> 必须 FAIL', not r1, 'verify_v1()=%s' % r1)

    # 负例 2：.SF 去掉 X-Android-APK-Signed（并重签 .RSA）
    bad2 = make_fake_zip(os.path.join(tmp, 'v1_nohdr.zip'), mod, key, cert,
                         [('a.txt', b'aaa')],
                         sf_mutator=lambda s: s.replace(
                             b'X-Android-APK-Signed: 2, 3\r\n', b''))
    with zipfile.ZipFile(bad2) as z:
        r2 = mod.verify_v1(z)
    report('P3b', '缺 X-Android-APK-Signed -> 必须 FAIL', not r2, 'verify_v1()=%s' % r2)

    # 负例 3：头存在但值不对（只声明 2）
    bad3 = make_fake_zip(os.path.join(tmp, 'v1_badhdr.zip'), mod, key, cert,
                         [('a.txt', b'aaa')],
                         sf_mutator=lambda s: s.replace(
                             b'X-Android-APK-Signed: 2, 3\r\n',
                             b'X-Android-APK-Signed: 2\r\n'))
    with zipfile.ZipFile(bad3) as z:
        r3 = mod.verify_v1(z)
    report('P3c', 'X-Android-APK-Signed 值不对 -> 必须 FAIL', not r3,
           'verify_v1()=%s' % r3)

    # 负例 4：META-INF 下残留旧签名
    bad4 = os.path.join(tmp, 'v1_stale.zip')
    with zipfile.ZipFile(base) as z:
        names = z.namelist()
    with zipfile.ZipFile(base) as z, zipfile.ZipFile(bad4, 'w', zipfile.ZIP_STORED) as o:
        for n in names:
            o.writestr(n, z.read(n))
        o.writestr('META-INF/BACN.RSA', b'stale')
        o.writestr('META-INF/BACN.SF', b'stale')
    with zipfile.ZipFile(bad4) as z:
        r4 = mod.verify_v1(z)
    report('P3d', 'META-INF 残留旧签名 -> 必须 FAIL', not r4, 'verify_v1()=%s' % r4)

    # 负例 5：zip 里有 MANIFEST 未覆盖的条目
    bad5 = os.path.join(tmp, 'v1_uncovered.zip')
    with zipfile.ZipFile(base) as z:
        names = z.namelist()
    with zipfile.ZipFile(base) as z, zipfile.ZipFile(bad5, 'w', zipfile.ZIP_STORED) as o:
        for n in names:
            o.writestr(n, z.read(n))
        o.writestr('assets/extra_not_in_manifest.bin', b'zzz')
    with zipfile.ZipFile(bad5) as z:
        r5 = mod.verify_v1(z)
    report('P3e', '有不被 MANIFEST 覆盖的条目 -> 必须 FAIL', not r5,
           'verify_v1()=%s' % r5)
    return bool(good and not r1 and not r2 and not r3 and not r4 and not r5)


def t4_pairing(mod, tmp, key, cert, key2, cert2):
    src = make_tiny(os.path.join(tmp, 'tiny_pair.apk'))
    out = os.path.join(tmp, 'pair_out.apk')
    died = False
    detail = ''
    try:
        mod.do_build(src, out, None, None, 'user', key2, cert)
    except SystemExit as ex:
        died = True
        detail = 'SystemExit(%s)' % ex.code
    except Exception as ex:
        died = True
        detail = '%r' % (ex,)
    reported = died
    if not died:
        # 未拒绝：证明产出的 v2 块里"签名者公钥 != 证书公钥"
        cert_der, pub = v2_cert_and_pub(out)
        spki = cert_spki_of(cert_der) if cert_der else None
        detail = 'do_build 未拒绝；v2 pub==cert SPKI? %s' % (spki == pub)
        reported = False
    report('P4', 'cert/私钥不配对 -> 拒绝构建', reported, detail)
    return reported


def t5_arsc(mod, tmp, key, cert):
    # (a) 源包 arsc 是 DEFLATE -> 输出必须变 STORED
    src = make_tiny(os.path.join(tmp, 'tiny_arsc.zip'), arsc_method=8)
    with zipfile.ZipFile(src) as z:
        src_method = z.getinfo('resources.arsc').compress_type
    out = os.path.join(tmp, 'arsc_out.apk')
    mod.do_build(src, out, None, None, 'user', key, cert, v1_on=True)
    with zipfile.ZipFile(out) as z:
        out_method = z.getinfo('resources.arsc').compress_type
        out_first = z.namelist()[0]
    ok_a = (out_method == 0)
    report('P5', 'DEFLATE 源 arsc -> 输出强制 STORED', ok_a,
           'src method=%d -> out method=%d, first=%s' % (src_method, out_method, out_first))

    # (b) 构造一个"签名全都对、但 arsc 是 DEFLATE"的包，verify() 必须硬失败
    orig_add = mod.ZipWriter.add

    def patched_add(self, name, method, crc, csize, usize, dt, feeder, v1sink=None):
        if name == 'resources.arsc' and method == 0:
            data = b''.join(feeder)
            co = zlib.compressobj(9, zlib.DEFLATED, -15)
            comp = co.compress(data) + co.flush()
            return orig_add(self, name, 8, zlib.crc32(data) & 0xFFFFFFFF,
                            len(comp), len(data), dt, [comp], v1sink)
        return orig_add(self, name, method, crc, csize, usize, dt, feeder, v1sink)

    bad = os.path.join(tmp, 'arsc_deflate_signed.apk')
    mod.ZipWriter.add = patched_add
    try:
        src2 = make_tiny(os.path.join(tmp, 'tiny_arsc2.zip'), arsc_method=0)
        mod.do_build(src2, bad, None, None, 'user', key, cert, v1_on=True)
    finally:
        mod.ZipWriter.add = orig_add
    with zipfile.ZipFile(bad) as z:
        bad_method = z.getinfo('resources.arsc').compress_type
    ok_verify = mod.verify(bad)
    report('P5b', 'arsc 非 STORED 的包 -> verify() 硬失败', not ok_verify,
           'arsc method=%d, verify()=%s' % (bad_method, ok_verify))
    return ok_a and not ok_verify


def t6_identity(mod, tmp, key, cert):
    # (a) 包名不对 -> 拒绝
    bad_src = make_tiny(os.path.join(tmp, 'tiny_badpkg.apk'),
                        pkg='com.example.notbluearchive')
    out = os.path.join(tmp, 'badpkg_out.apk')
    died = False
    detail = ''
    try:
        mod.do_build(bad_src, out, None, None, 'user', key, cert)
    except SystemExit as ex:
        died = True
        detail = 'SystemExit(%s)' % ex.code
    report('P6', '包名不符 -> 拒绝构建', died, detail)

    # (b) --force 可跳过
    forced_ok = False
    detail2 = ''
    try:
        mod.do_build(bad_src, out + '2', None, None, 'user', key, cert, force=True)
        forced_ok = os.path.exists(out + '2')
        detail2 = 'force=True 构建成功'
    except TypeError:
        detail2 = 'do_build 没有 force 参数'
    except SystemExit as ex:
        detail2 = 'force=True 仍被拒绝 SystemExit(%s)' % ex.code
    report('P6b', '--force 可跳过身份校验', forced_ok, detail2)

    # (c) v3 的 minSdk 必须来自 manifest（源包写 21，v3 就应是 21）
    src21 = make_tiny(os.path.join(tmp, 'tiny_sdk21.apk'), min_sdk=21)
    out21 = os.path.join(tmp, 'sdk21_out.apk')
    got = None
    try:
        mod.do_build(src21, out21, None, None, 'user', key, cert)
        got = v3_minsdk(out21)
    except SystemExit as ex:
        got = 'SystemExit(%s)' % ex.code
    report('P6c', 'v3 minSdk 取自 manifest（源=21）', got == (21, 0x7FFFFFFF),
           'v3 min/max=%r' % (got,))
    return died and forced_ok and got == (21, 0x7FFFFFFF)


def t7_live(mod, apk):
    """对真产物只读复核：把它的 MANIFEST 条目喂给新的 build_v1，看会写出什么。"""
    if not os.path.exists(apk):
        return
    with zipfile.ZipFile(apk) as z:
        mf_old = z.read('META-INF/MANIFEST.MF')
        old_sf = z.read('META-INF/CERT.SF')
    main, secs = parse_manifest_liberal(mf_old)
    items = [(n, base64.b64decode(d['SHA-256-Digest'])) for n, d in secs]
    mf_new, sf_new = mod.build_v1(items)
    lens = [len(x) for x in mf_new.split(b'\r\n')]
    strict_main, strict_secs, viol = parse_manifest_strict(mf_new)
    liber_main, liber_secs = parse_manifest_liberal(mf_new)
    names_ok = ([n for n, _ in strict_secs] == [n for n, _ in liber_secs] ==
                [n for n, _ in secs])
    dig_ok = all(strict_secs[i][1].get('SHA-256-Digest') ==
                 base64.b64encode(items[i][1]).decode() for i in range(len(items)))
    sf_main, _ = parse_manifest_liberal(sf_new)
    hdr = sf_main.get('X-Android-APK-Signed')
    report('P7', '真包 41,304 条喂给新生成器：换行/拼回/摘要/头',
           names_ok and dig_ok and not viol and max(lens) <= 72 and hdr == '2, 3',
           'old: %d B/max %d/over72 %d/hdr %r | new: %d B/max %d/over72 %d/续行 %d/hdr %r'
           % (len(mf_old), max(len(x) for x in mf_old.split(b'\r\n')),
              sum(1 for x in mf_old.split(b'\r\n') if len(x) > 72),
              parse_manifest_liberal(old_sf)[0].get('X-Android-APK-Signed'),
              len(mf_new), max(lens), sum(1 for n in lens if n > 72),
              sum(1 for x in mf_new.split(b'\r\n') if x.startswith(b' ')), hdr))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--module', default=os.path.join(HERE, 'build_noroot_apk.py'))
    ap.add_argument('--live', default=os.path.join(HERE, 'BA_noroot_v1.apk'))
    ap.add_argument('--skip-live', action='store_true')
    a = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    print('[*] 被测模块: %s (%d B)' % (a.module, os.path.getsize(a.module)))
    mod = load_module(a.module)
    tmp = tempfile.mkdtemp(prefix='sigfixtest')
    print('[*] 临时目录: %s' % tmp)
    print('[*] 生成两对 RSA-1024 密钥（约 1 s）')
    k1 = mod.rsa_generate(1024)
    c1 = mod.build_self_signed_cert(k1, cn='ba')
    k2 = mod.rsa_generate(1024)
    c2 = mod.build_self_signed_cert(k2, cn='ba2')

    t1_sf_header(mod, tmp, k1, c1)
    t2_wrap(mod, tmp, k1, c1)
    t3_verify_v1(mod, tmp, k1, c1)
    t4_pairing(mod, tmp, k1, c1, k2, c2)
    t5_arsc(mod, tmp, k1, c1)
    t6_identity(mod, tmp, k1, c1)
    if not a.skip_live:
        t7_live(mod, a.live)

    npass = sum(1 for r in RESULTS if r[2] == 'OK')
    print('\n[*] 合计 %d/%d 通过' % (npass, len(RESULTS)))
    fails = [r for r in RESULTS if r[2] != 'OK']
    if fails:
        print('[*] 未通过：')
        for pid, title, _s, detail in fails:
            print('    %-4s %s  %s' % (pid, title, detail))
    return 0 if not fails else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
