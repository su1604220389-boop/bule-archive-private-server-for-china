#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_noroot_apk.py -- BA 国服（com.RoamingStar.BlueArchive）免 root 改造包构建器

单文件、纯 Python 3 标准库。不需要 apktool / aapt2 / jarsigner / keytool / zipalign / apksigner。
自己实现：AXML 生成、ZIP 重打包（对齐）、APK Signature Scheme v1/v2/v3、
RSA 密钥与自签 X.509 证书、PKCS#7。

改造 6 步（对应 NOROOT_BUILD.md）：
  ① res/Dk.xml 重写 network security config（加 <trust-anchors>）
  ② assets/SDKConfigSettings.json 改 sdk_url
  ③ 删 assets/__tpinfo.{tp,tsc,tsc.sig,tsd,tsd.sig}   （不删必闪退）
  ④ （可选）把 CA 打进 APK：复用唯一的 raw 槽 res/E5.ogg，src 用资源引用
  ⑤ 重打包：resources.arsc 置首 + STORED + 4 字节对齐
  ⑥ 重签 v1 + v2 + v3

用法：
  python build_noroot_apk.py --gen-keystore ba_private.keystore
  python build_noroot_apk.py --src <base.apk> --out <out.apk> ^
        --sdk-url https://<卡密服务> ^
        --keystore ba_private.keystore --storepass baserver --alias ba
  python build_noroot_apk.py --src ... --out ... --ca our_ca.crt --ca-mode both
  python build_noroot_apk.py --verify-only <out.apk>
  python build_noroot_apk.py --self-test

state 入口（GameMainConfig / ServerInfoDataUrl，等长替换，见 GMCONFIG_INTEGRATION.md）：
  python build_noroot_apk.py --src <base.apk> --out <out.apk> ^
        --gmconfig-url bapsvr-prods-cn.com        # 19 字符 http 域名（最优，余量刚好为 0）
  python build_noroot_apk.py ... --gmconfig-url http://state-api.x.com/api/state
  python build_noroot_apk.py ... --gmconfig-value '["http://x/api/state"]'
  python build_noroot_apk.py ... --asset-replace assets/bin/Data/e37c46fe...=<本地 bin>
  python build_noroot_apk.py --src <base.apk> --gmconfig-selftest   # 不构建，只测替换算法

退出码：0 成功；1 校验失败；2 环境不足
"""

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zlib

# ---------------------------------------------------------------------------
# 0. 实测常量（report\_tmp\cn_base.apk = 2,126,400,085 B / 41,312 entries）
# ---------------------------------------------------------------------------
PKG_NAME = 'com.RoamingStar.BlueArchive'
APK_VERSION_NAME = '3.0.2'
APK_VERSION_CODE = 73
MIN_SDK = 24
TARGET_SDK = 33

NSC_RES_ID = 0x7F120001          # android:networkSecurityConfig -> @xml/http
NSC_ENTRY = 'res/Dk.xml'         # arsc 里存的路径（AndResGuard 扁平混淆名，绝不能改）
SDKCFG_ENTRY = 'assets/SDKConfigSettings.json'
SPARE_RAW_RES_ID = 0x7F0E0000    # 唯一的 res/raw（key=zxing_beep）-> res/E5.ogg
SPARE_RAW_ENTRY = 'res/E5.ogg'

TPINFO_ENTRIES = [
    'assets/__tpinfo.tp',
    'assets/__tpinfo.tsc',
    'assets/__tpinfo.tsc.sig',
    'assets/__tpinfo.tsd',
    'assets/__tpinfo.tsd.sig',
]

# 旧 v1 签名文件必须整组剔除，否则会和重新生成的同名（zip 不允许重名，Android 直接拒装）
OLD_SIG_RE = re.compile(r'^META-INF/(MANIFEST\.MF|[^/]*\.(SF|RSA|DSA|EC)|SIG-[^/]*)$',
                        re.IGNORECASE)


def is_old_signature(name):
    return bool(OLD_SIG_RE.match(name))


# ---------------------------------------------------------------------------
# 0b. GameMainConfig（国服 state 入口）实测布局 —— GAMEMAINCONFIG_CN.md §3/§9
#     assets/bin/Data/e37c46fea17834108a4756797197d05a  5,212 B
#     0x1000 u32 名称长=14 | 0x1004 "GameMainConfig" | 0x1012 对齐 2B
#     0x1014 u32 m_Script 长=1090 | 0x1018..0x145A 密文 | 0x145A 对齐 2B
#     密文 = UTF-16LE(JSON) XOR cycle8(create_key("GameMainConfig"))
#     m_Script 固定 1090 B = 545 个 UTF-16 字符，余量 0 ⇒ 只能等长替换
# ---------------------------------------------------------------------------
GMC_ENTRY = 'assets/bin/Data/e37c46fea17834108a4756797197d05a'
GMC_NAME = 'GameMainConfig'
GMC_SIZE = 5212
GMC_NAMELEN = 14
GMC_NAME_OFF = 0x1000            # u32 名称长度
GMC_SCRIPT_OFF = 0x1018          # 密文起点
GMC_LEN_OFF = 0x1014             # u32 m_Script 长度
GMC_SCRIPT_LEN = 1090
GMC_URL_FIELD = 'ServerInfoDataUrl'
GMC_FIELDS = ('SkipTutorial', 'ServerInfoDataUrl', 'ServerName',
              'VersionCode', 'PlatformID', 'ChannelID')
# 国服两条 dispatcher 模板（只换域名/协议，路径与条数不变 ⇒ 长度可控）
GMC_TMPL_PAIR = ('["{scheme}://state-api.{domain}/api/state",'
                 '"{scheme}://stateqc-api.{domain}/api/state"]')
GMC_HOST_PREFIXES = (('stateqc-api.', 12), ('state-api.', 10))

# JAR 清单行长度上限（内容字节，不含 CRLF）。官方 cn_base.apk 实测最长 70 B。
JAR_MAX_LINE = 70

MAX32 = 0x7FFFFFFF               # >2^31-1 就要 Zip64，会破坏对齐假设
ALIGN_EXTRA_ID = 0xD935          # signapk 的「对齐 extra 字段」header id
CHUNK = 1024 * 1024              # v2/v3 分块摘要块大小
SIG_ALG_RSA_PKCS1_SHA256 = 0x0103
V2_BLOCK_ID = 0x7109871A
V3_BLOCK_ID = 0xF05368C0
MAGIC = b'APK Sig Block 42'

# ---- v1（JAR）签名常量 -----------------------------------------------------
# JAR 清单规范：每行（UTF-8 编码后，不含 CRLF）最多 72 B，超了拆续行（续行首字节是空格）。
# signapk / apksig 的 ManifestWriter 用的是 70（实测 apksig-8.6.1 的
# internal/jar/ManifestWriter.class 常量池里只有 Integer 70），原厂 cn_base.apk 的
# MANIFEST.MF / BACN.SF 行长也是 max=70、0 行 >72、1,254 条续行。为字节风格一致取 70。
JAR_LINE_MAX = 70
JAR_LINE_SPEC_MAX = 72           # 规范硬上限，校验时按这个判定
SIG_SCHEMES = (2, 3)             # 本工具产出的方案；写进 .SF 的 X-Android-APK-Signed
MF_ENTRY = 'META-INF/MANIFEST.MF'
SF_ENTRY = 'META-INF/CERT.SF'
RSA_ENTRY = 'META-INF/CERT.RSA'
SIG_ENTRIES = (MF_ENTRY, SF_ENTRY, RSA_ENTRY)
ARSC = 'resources.arsc'


def log(m=''):
    print(m, flush=True)


def die(m, code=1):
    print('ERROR: ' + m, file=sys.stderr, flush=True)
    raise SystemExit(code)


def human(n):
    f, u = float(n), 'B'
    for u in ('B', 'KB', 'MB', 'GB'):
        if f < 1024 or u == 'GB':
            return ('%d %s' % (f, u)) if u == 'B' else ('%.2f %s' % (f, u))
        f /= 1024.0


# ---------------------------------------------------------------------------
# 1. 最小 DER
# ---------------------------------------------------------------------------
def der_tlv(tag, v):
    n = len(v)
    if n < 0x80:
        return bytes([tag, n]) + v
    lb = n.to_bytes((n.bit_length() + 7) // 8, 'big')
    return bytes([tag, 0x80 | len(lb)]) + lb + v


def der_seq(*i):
    return der_tlv(0x30, b''.join(i))


def der_set(*i):
    return der_tlv(0x31, b''.join(i))


def der_int(v):
    b = v.to_bytes(max(1, (v.bit_length() + 7) // 8), 'big')
    return der_tlv(0x02, (b'\x00' + b) if b[0] & 0x80 else b)


def der_octet(b):
    return der_tlv(0x04, b)


def der_null():
    return b'\x05\x00'


def der_bitstring(b):
    return der_tlv(0x03, b'\x00' + b)


def der_oid(dotted):
    p = [int(x) for x in dotted.split('.')]
    out = bytes([p[0] * 40 + p[1]])
    for v in p[2:]:
        if v < 0x80:
            out += bytes([v])
        else:
            t = []
            while v:
                t.append(v & 0x7F)
                v >>= 7
            t.reverse()
            for i in range(len(t) - 1):
                t[i] |= 0x80
            out += bytes(t)
    return der_tlv(0x06, out)


def der_utf8(s):
    return der_tlv(0x0C, s.encode('utf-8'))


def der_read_tlv(buf, off):
    tag = buf[off]
    l = buf[off + 1]
    o = off + 2
    if l & 0x80:
        nb = l & 0x7F
        l = int.from_bytes(buf[o:o + nb], 'big')
        o += nb
    return tag, o, l, o + l


def der_children(buf, off, end):
    out = []
    while off < end:
        tag, vo, vl, nx = der_read_tlv(buf, off)
        out.append((tag, vo, vl, off, nx))
        off = nx
    return out


OID_SHA256 = '2.16.840.1.101.3.4.2.1'
OID_RSA = '1.2.840.113549.1.1.1'
OID_SHA256_RSA = '1.2.840.113549.1.1.11'
OID_P7_SIGNED = '1.2.840.113549.1.7.2'
OID_P7_DATA = '1.2.840.113549.1.7.1'
OID_P7_MESSAGEDIGEST = '1.2.840.113549.1.9.4'
OID_CN, OID_OU, OID_O, OID_C = '2.5.4.3', '2.5.4.11', '2.5.4.10', '2.5.4.6'
OID_BASIC_CONSTRAINTS = '2.5.29.19'


# ---------------------------------------------------------------------------
# 2. RSA
# ---------------------------------------------------------------------------
def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a


_SMALL = [p for p in range(3, 3000, 2) if all(p % d for d in range(3, int(p ** 0.5) + 1, 2))]


def _is_prime(n, rounds=40):
    if n < 2:
        return False
    for p in _SMALL:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def rsa_generate(bits=2048, e=65537, progress=None):
    if progress:
        progress('RSA-%d 生成素对...' % bits)
    half = bits // 2
    while True:
        p = q = 0
        while not p:
            c = secrets.randbits(half) | (1 << (half - 1)) | 1
            if c % e != 1 and _is_prime(c):
                p = c
        while not q:
            c = secrets.randbits(half) | (1 << (half - 1)) | 1
            if c != p and c % e != 1 and _is_prime(c):
                q = c
        if p < q:
            p, q = q, p
        n = p * q
        if n.bit_length() != bits:
            continue
        lam = (p - 1) * (q - 1) // _gcd(p - 1, q - 1)
        if _gcd(e, lam) != 1:
            continue
        d = pow(e, -1, lam)
        return {'n': n, 'e': e, 'd': d, 'p': p, 'q': q,
                'dp': d % (p - 1), 'dq': d % (q - 1), 'qinv': pow(q, -1, p),
                'bits': bits}


def _k(key):
    return (key['n'].bit_length() + 7) // 8


def rsa_public_der(key):
    return der_seq(der_seq(der_oid(OID_RSA), der_null()),
                   der_bitstring(der_seq(der_int(key['n']), der_int(key['e']))))


def _em(h32, k):
    di = der_seq(der_seq(der_oid(OID_SHA256), der_null()), der_octet(h32))
    if len(di) + 11 > k:
        die('RSA 模长太小')
    return b'\x00\x01' + b'\xff' * (k - len(di) - 3) + b'\x00' + di


def rsa_sign_sha256(key, data):
    k = _k(key)
    m = int.from_bytes(_em(hashlib.sha256(data).digest(), k), 'big')
    return pow(m, key['d'], key['n']).to_bytes(k, 'big')


def rsa_verify_sha256(n, e, data, sig):
    k = (n.bit_length() + 7) // 8
    if len(sig) != k:
        return False, 'sig len %d != k %d' % (len(sig), k)
    em = pow(int.from_bytes(sig, 'big'), e, n).to_bytes(k, 'big')
    return (em == _em(hashlib.sha256(data).digest(), k), 'ok')


# ---- PEM ------------------------------------------------------------------
def pem_wrap(label, der):
    b = base64.b64encode(der).decode()
    return '-----BEGIN %s-----\n%s\n-----END %s-----\n' % (
        label, '\n'.join(b[i:i + 64] for i in range(0, len(b), 64)), label)


def pem_blocks(text):
    return [(m.group(1), base64.b64decode(''.join(m.group(2).split())))
            for m in re.finditer(r'-----BEGIN ([A-Z0-9 ]+)-----(.*?)-----END \1-----',
                                 text, re.S)]


def rsa_private_pem(key):
    return pem_wrap('RSA PRIVATE KEY', der_seq(
        der_int(0), der_int(key['n']), der_int(key['e']), der_int(key['d']),
        der_int(key['p']), der_int(key['q']), der_int(key['dp']),
        der_int(key['dq']), der_int(key['qinv'])))


def parse_rsa_der(der):
    """同时吃 PKCS#1 RSAPrivateKey 与 PKCS#8 PrivateKeyInfo"""
    _, vo, vl, _ = der_read_tlv(der, 0)
    kids = der_children(der, vo, vo + vl)
    if (len(kids) == 3 and kids[0][0] == 0x02 and kids[1][0] == 0x30
            and kids[2][0] == 0x04):
        k2 = kids[2]
        return parse_rsa_der(der[k2[1]:k2[1] + k2[2]])
    ints = [int.from_bytes(der[a:a + b], 'big') for (t, a, b, _, _) in kids if t == 0x02]
    if len(ints) < 6:
        raise ValueError('不是 RSA 私钥结构')
    _, n, e, d, p, q = ints[:6]
    if not (n and d and p and q and e):
        raise ValueError('RSA 私钥字段为 0')
    dp = ints[6] if len(ints) > 6 else d % (p - 1)
    dq = ints[7] if len(ints) > 7 else d % (q - 1)
    qinv = ints[8] if len(ints) > 8 else pow(q, -1, p)
    return {'n': n, 'e': e, 'd': d, 'p': p, 'q': q, 'dp': dp, 'dq': dq,
            'qinv': qinv, 'bits': n.bit_length()}


def rsa_key_from_pem(text):
    for label, der in pem_blocks(text):
        if label in ('RSA PRIVATE KEY', 'PRIVATE KEY'):
            return parse_rsa_der(der)
    raise ValueError('PEM 里没有 RSA 私钥（支持 PKCS#1 / PKCS#8）')


# ---------------------------------------------------------------------------
# 3. 自签 X.509
# ---------------------------------------------------------------------------
def build_self_signed_cert(key, cn='BA', ou='Private', o='BA', c='CN',
                           serial=None, ca=True):
    import datetime
    if serial is None:
        serial = secrets.randbits(62) | (1 << 61)
    nb = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
    na = datetime.datetime(2049, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc)
    name = der_seq(
        der_set(der_seq(der_oid(OID_C), der_utf8(c))),
        der_set(der_seq(der_oid(OID_O), der_utf8(o))),
        der_set(der_seq(der_oid(OID_OU), der_utf8(ou))),
        der_set(der_seq(der_oid(OID_CN), der_utf8(cn))))
    sigalg = der_seq(der_oid(OID_SHA256_RSA), der_null())
    exts = b''
    if ca:
        # basicConstraints: cA=TRUE  ->  SEQUENCE { BOOLEAN TRUE }
        exts = der_tlv(0xA3, der_seq(
            der_seq(der_oid(OID_BASIC_CONSTRAINTS), der_octet(der_seq(b'\x01\x01\xff')))))
    tbs = der_seq(
        der_tlv(0xA0, der_int(2)),
        der_int(serial),
        sigalg,
        name,
        der_seq(der_tlv(0x17, nb.strftime('%y%m%d%H%M%SZ').encode()),
                der_tlv(0x17, na.strftime('%y%m%d%H%M%SZ').encode())),
        name,
        rsa_public_der(key),
        exts)
    return der_seq(tbs, sigalg, der_bitstring(rsa_sign_sha256(key, tbs)))


def cert_serial_and_issuer(cert):
    _, vo, vl, _ = der_read_tlv(cert, 0)
    kids = der_children(cert, vo, vo + vl)
    tbs = kids[0]
    tk = der_children(cert, tbs[1], tbs[1] + tbs[2])
    i = 1 if tk[0][0] == 0xA0 else 0
    s = tk[i]
    iss = tk[i + 2]
    return (int.from_bytes(cert[s[1]:s[1] + s[2]], 'big'), cert[iss[3]:iss[4]])


def cert_spki(cert):
    """取证书的 SubjectPublicKeyInfo（DER 片段）。"""
    _, vo, vl, _ = der_read_tlv(cert, 0)
    kids = der_children(cert, vo, vo + vl)
    tbs = kids[0]
    tk = der_children(cert, tbs[1], tbs[1] + tbs[2])
    i = 1 if tk[0][0] == 0xA0 else 0
    # tk[i]=serial, i+1=sigAlg, i+2=issuer, i+3=validity, i+4=subject, i+5=SPKI
    if len(tk) < i + 6:
        raise ValueError('tbsCertificate 字段不足（%d）' % len(tk))
    spki = tk[i + 5]
    return cert[spki[3]:spki[4]]


def cert_pub_n_e(cert):
    return _parse_spki(cert_spki(cert))


def assert_key_pair(key, cert, where=''):
    """AUDIT P1-4：证书公钥必须 == 私钥公钥，否则 v2/v3 会被 Android 直接拒装。"""
    try:
        cn, ce = cert_pub_n_e(cert)
    except Exception as ex:
        die('%s证书解析失败：%r' % (where, ex))
    if cn != key['n'] or ce != key['e']:
        die('%s私钥与证书不配对：\n'
            '  私钥 n = %d bit, e = %d\n'
            '  证书 n = %d bit, e = %d\n'
            '  （v2/v3 要求 signer 公钥 == 第一张证书公钥，不配对会被 '
            'INSTALL_PARSE_FAILED_NO_CERTIFICATES 一类拒装）'
            % (where, key['n'].bit_length(), key['e'],
               cn.bit_length(), ce))
    return cn == key['n'] and ce == key['e']


# ---------------------------------------------------------------------------
# 4. PKCS#7 detached SignedData（META-INF/CERT.RSA）
# ---------------------------------------------------------------------------
def pkcs7_signed_data(key, cert, content):
    digest_alg = der_seq(der_oid(OID_SHA256), der_null())
    serial, issuer = cert_serial_and_issuer(cert)
    signer_info = der_seq(
        der_int(1),
        der_seq(issuer, der_int(serial)),
        digest_alg,
        der_seq(der_oid(OID_RSA), der_null()),
        der_octet(rsa_sign_sha256(key, content)))
    signed_data = der_seq(
        der_int(1),
        der_set(digest_alg),
        der_seq(der_oid(OID_P7_DATA)),
        der_tlv(0xA0, cert),
        der_set(signer_info))
    return der_seq(der_oid(OID_P7_SIGNED), der_tlv(0xA0, signed_data))


# ---------------------------------------------------------------------------
# 5. AXML 生成
# ---------------------------------------------------------------------------
class StringPool:
    def __init__(self):
        self.items, self.index = [], {}

    def add(self, s):
        if s not in self.index:
            self.index[s] = len(self.items)
            self.items.append(s)
        return self.index[s]

    def build(self):
        body = bytearray()
        offs = []
        for s in self.items:
            offs.append(len(body))
            b = s.encode('utf-8')
            n16 = len(s.encode('utf-16-le')) // 2
            for n in (n16, len(b)):
                if n > 0x7F:
                    body += bytes([0x80 | ((n >> 8) & 0x7F), n & 0xFF])
                else:
                    body += bytes([n])
            body += b + b'\x00'
        head = 28 + 4 * len(self.items)
        pad = (-(head + len(body))) % 4
        body += b'\x00' * pad
        return (struct.pack('<HHIIIIII', 0x0001, 28, head + len(body),
                            len(self.items), 0, 0x100, head, 0)
                + b''.join(struct.pack('<I', o) for o in offs) + bytes(body))


class Axml:
    def __init__(self):
        self.pool, self.chunks, self.line = StringPool(), [], 1

    def start(self, tag, attrs=()):
        ti = self.pool.add(tag)
        ab = b''
        for (an, dt, data, raw) in attrs:
            # 属性记录固定 20 B：ns(4) name(4) rawValue(4) + Res_value(2+1+1+4)
            ab += struct.pack('<IIIHBBI', 0xFFFFFFFF, self.pool.add(an), raw,
                              8, 0, dt, data)
        self.chunks.append(struct.pack('<HHIIIIIHHHHHH',
                                       0x0102, 16, 36 + 20 * len(attrs),
                                       self.line, 0xFFFFFFFF, 0xFFFFFFFF,
                                       ti, 20, 20, len(attrs), 0, 0, 0) + ab)
        self.line += 1

    def end(self, tag):
        self.chunks.append(struct.pack('<HHIIIII', 0x0103, 16, 24, self.line,
                                       0xFFFFFFFF, 0xFFFFFFFF, self.pool.add(tag)))
        self.line += 1

    def build(self):
        body = (self.pool.build() + struct.pack('<HHI', 0x0180, 8, 8)
                + b''.join(self.chunks))
        return struct.pack('<HHI', 0x0003, 8, 8 + len(body)) + body


def build_nsc_axml(ca_mode='user', ca_res_id=SPARE_RAW_RES_ID):
    """生成 network security config 的二进制 AXML。

    ca_mode:
      'user'    系统 CA + 用户 CA（推荐；用户装一次证书即可）
      'system'  只系统 CA
      'both'    系统 CA + 用户 CA + APK 内置 CA（资源引用）
      'bundled' 系统 CA + APK 内置 CA

    注意（AOSP NetworkSecurityConfig.Builder）：base-config 里一旦出现
    <trust-anchors>，就**完全取代**平台默认信任集，不会与默认集合并。
    所以必须显式列出 system，否则公开 HTTPS 全挂。
    """
    a = Axml()
    a.start('network-security-config')
    a.start('base-config', [('cleartextTrafficPermitted', 0x12, 0xFFFFFFFF, 0xFFFFFFFF)])
    a.start('trust-anchors')
    if ca_mode in ('user', 'system', 'both', 'bundled'):
        i = a.pool.add('system')
        a.start('certificates', [('src', 0x03, i, i)])
        a.end('certificates')
    if ca_mode in ('user', 'both'):
        i = a.pool.add('user')
        a.start('certificates', [('src', 0x03, i, i)])
        a.end('certificates')
    if ca_mode in ('both', 'bundled'):
        # TYPE_REFERENCE(0x01)；框架先查 getAttributeResourceValue(null,"src",-1)
        a.start('certificates', [('src', 0x01, ca_res_id, 0xFFFFFFFF)])
        a.end('certificates')
    a.end('trust-anchors')
    a.end('base-config')
    a.end('network-security-config')
    return a.build()


def axml_parse(buf):
    typ, hsz, _ = struct.unpack_from('<HHI', buf, 0)
    if typ != 0x0003:
        raise ValueError('not axml')
    off, pool, ev = hsz, [], []
    while off + 8 <= len(buf):
        ct, ch, cs = struct.unpack_from('<HHI', buf, off)
        if cs < 8:
            break
        if ct == 0x0001:
            cnt, sty, fl, ss, _x = struct.unpack_from('<IIIII', buf, off + 8)
            utf8 = bool(fl & 0x100)
            offs = struct.unpack_from('<%dI' % cnt, buf, off + ch)
            for o in offs:
                p = off + ss + o
                if utf8:
                    p += 1
                    n = buf[p]
                    p += 1
                    if n & 0x80:
                        n = ((n & 0x7F) << 8) | buf[p]
                        p += 1
                    pool.append(buf[p:p + n].decode('utf-8', 'replace'))
                else:
                    n = struct.unpack_from('<H', buf, p)[0]
                    p += 2
                    pool.append(buf[p:p + n * 2].decode('utf-16-le', 'replace'))
        elif ct == 0x0102:
            nm = struct.unpack_from('<I', buf, off + 20)[0]
            ast, asz, ac = struct.unpack_from('<HHH', buf, off + 24)
            attrs, p = [], off + 16 + ast
            for _i in range(ac):
                _ns, an, ar = struct.unpack_from('<III', buf, p)
                _sz, _r0, dt, data = struct.unpack_from('<HBBI', buf, p + 12)
                attrs.append({'name': pool[an], 'dtype': dt, 'data': data,
                              'sval': (pool[data] if dt == 0x03 and 0 <= data < len(pool)
                                       else None)})
                p += asz
            ev.append({'tag': pool[nm], 'attrs': attrs})
        elif ct == 0x0103:
            ev.append({'end': pool[struct.unpack_from('<I', buf, off + 20)[0]]})
        off += cs
    return ev


def axml_text(ev):
    out, d = [], 0
    for e in ev:
        if 'end' in e:
            d -= 1
            out.append('  ' * max(0, d) + '</%s>' % e['end'])
            continue
        a = []
        for at in e['attrs']:
            if at['dtype'] == 0x12:
                a.append('%s="%s"' % (at['name'], 'true' if at['data'] else 'false'))
            elif at['dtype'] == 0x03:
                a.append('%s="%s"' % (at['name'],
                                      at['sval'] if at['sval'] is not None else at['data']))
            elif at['dtype'] == 0x01:
                a.append('%s=&quot;@0x%08x&quot;' % (at['name'], at['data']))
            else:
                a.append('%s=0x%x:0x%x' % (at['name'], at['dtype'], at['data']))
        out.append('  ' * d + '<%s%s>' % (e['tag'], (' ' + ' '.join(a)) if a else ''))
        d += 1
    return '\n'.join(out)


# ---------------------------------------------------------------------------
# 6. 源 ZIP（流式读取，保留原始压缩流）
# ---------------------------------------------------------------------------
class SrcZip:
    def __init__(self, path):
        import zipfile
        self.path = path
        self.f = open(path, 'rb')
        self.size = os.path.getsize(path)
        zf = zipfile.ZipFile(path)
        self.entries = []
        for zi in zf.infolist():
            if zi.compress_type not in (0, 8):
                die('不支持的压缩方法 %d: %s' % (zi.compress_type, zi.filename))
            self.entries.append({'name': zi.filename, 'method': zi.compress_type,
                                 'crc': zi.CRC, 'csize': zi.compress_size,
                                 'usize': zi.file_size, 'dt': zi.date_time,
                                 'hdr': zi.header_offset})
        zf.close()
        self.by_name = {e['name']: e for e in self.entries}

    def has(self, n):
        return n in self.by_name

    def data_offset(self, name):
        e = self.by_name[name]
        self.f.seek(e['hdr'])
        h = self.f.read(30)
        sig, _v, _f, _m, _t, _d, _c, _cs, _us, nl, el = struct.unpack('<IHHHHHIIIHH', h)
        if sig != 0x04034B50:
            die('本地头签名错误: %s' % name)
        return e['hdr'] + 30 + nl + el

    def chunks(self, name, bs=CHUNK):
        e = self.by_name[name]
        self.f.seek(self.data_offset(name))
        left = e['csize']
        while left > 0:
            b = self.f.read(min(bs, left))
            if not b:
                break
            left -= len(b)
            yield b

    def read(self, name):
        e = self.by_name[name]
        raw = b''.join(self.chunks(name))
        return raw if e['method'] == 0 else zlib.decompress(raw, -15)

    def close(self):
        self.f.close()


# ---------------------------------------------------------------------------
# 7. ZIP 写入 + v2/v3 内容摘要
# ---------------------------------------------------------------------------
class ChunkHasher:
    """AOSP ApkSigningBlockUtils.computeContentDigestsPer1MbChunk

    每块：digest_i = SHA256(0xA5 | u32le(len) | chunk_i)
    最终：SHA256(0x5A | u32le(块数) | digest_0 | digest_1 | ...)
    空段不产生分块；块数跨三个段累计。
    """

    def __init__(self):
        self.chunks = []          # 2.1 GB / 1 MiB ≈ 2030 块 × 32 B ≈ 65 KB
        self.buf = bytearray()

    def update(self, b):
        self.buf += b
        while len(self.buf) >= CHUNK:
            self._emit(bytes(self.buf[:CHUNK]))
            del self.buf[:CHUNK]

    def _emit(self, c):
        self.chunks.append(hashlib.sha256(
            b'\xa5' + struct.pack('<I', len(c)) + c).digest())

    def digest(self, extra_segments=()):
        if self.buf:
            self._emit(bytes(self.buf))
            del self.buf[:]
        chunks = list(self.chunks)
        for seg in extra_segments:
            for i in range(0, len(seg), CHUNK):
                c = seg[i:i + CHUNK]
                chunks.append(hashlib.sha256(
                    b'\xa5' + struct.pack('<I', len(c)) + c).digest())
        return hashlib.sha256(
            b'\x5a' + struct.pack('<I', len(chunks)) + b''.join(chunks)).digest()


class ZipWriter:
    def __init__(self, path, align_mode='raw'):
        self.path = path
        self.f = open(path, 'wb')
        self.pos = 0
        self.cd = []
        self.align_mode = align_mode
        self.chunk1 = ChunkHasher()
        self.n_stored = self.n_defl = 0
        self.names = set()

    def _w(self, b):
        self.f.write(b)
        self.pos += len(b)
        self.chunk1.update(b)

    def _extra(self, nlen, method):
        if method != 0 or self.align_mode == 'none':
            return b''
        if self.align_mode == 'raw':
            # zipalign 行为：extra 尾部补 0~3 个裸 0 字节。原包就是这个风格
            return b'\x00' * ((-(self.pos + 30 + nlen)) % 4)
        # signapk 的 0xD935：u16 id | u16(2+pad) | u16 align | pad*0x00
        pad = (-(self.pos + 30 + nlen + 6)) % 4
        return struct.pack('<HHH', ALIGN_EXTRA_ID, 2 + pad, 4) + b'\x00' * pad

    def add(self, name, method, crc, csize, usize, dt, feeder, v1sink=None):
        if name in self.names:
            die('zip 重名条目：%s（会直接导致装不上）' % name)
        self.names.add(name)
        nb = name.encode('utf-8')
        extra = self._extra(len(nb), method)
        ver = 10 if method == 0 else 20
        dosdate = ((dt[0] - 1980) << 9) | (dt[1] << 5) | dt[2]
        dostime = (dt[3] << 11) | (dt[4] << 5) | (dt[5] // 2)
        off = self.pos
        self._w(struct.pack('<IHHHHHIIIHH', 0x04034B50, ver, 0x0800, method,
                            dostime, dosdate, crc, csize, usize,
                            len(nb), len(extra)) + nb + extra)
        written = 0
        dec = zlib.decompressobj(-15) if (v1sink is not None and method == 8) else None
        for c in feeder:
            self._w(c)
            written += len(c)
            if v1sink is not None:
                v1sink.update(c if method == 0 else dec.decompress(c))
        if dec is not None:
            v1sink.update(dec.flush())
        if written != csize:
            die('%s 压缩流 %d != 声明 %d' % (name, written, csize))
        if method == 0:
            self.n_stored += 1
        else:
            self.n_defl += 1
        self.cd.append(struct.pack('<IHHHHHHIIIHHHHHII', 0x02014B50, 20, ver,
                                   0x0800, method, dostime, dosdate, crc, csize,
                                   usize, len(nb), len(extra), 0, 0, 0, 0, off)
                       + nb + extra)

    def close(self):
        self.f.close()


# ---------------------------------------------------------------------------
# 8. APK Signing Block
# ---------------------------------------------------------------------------
def lp(b):
    return struct.pack('<I', len(b)) + b


def build_v2_signer(digest, certs, pub, key):
    d = lp(struct.pack('<I', SIG_ALG_RSA_PKCS1_SHA256) + lp(digest))
    sd = lp(d) + lp(b''.join(lp(c) for c in certs)) + lp(b'')
    sg = lp(struct.pack('<I', SIG_ALG_RSA_PKCS1_SHA256) + lp(rsa_sign_sha256(key, sd)))
    signer = lp(sd) + lp(sg) + lp(pub)        # signer 结构体
    return lp(lp(signer))                     # value = lp(签名者序列)，序列内每个 signer 再 lp


def build_v3_signer(digest, certs, pub, key, minsdk, maxsdk):
    d = lp(struct.pack('<I', SIG_ALG_RSA_PKCS1_SHA256) + lp(digest))
    # v3 的 minSdk/maxSdk 是裸 uint32，不是「带 id 的字段」；签名值与未签名值必须一致
    sd = (lp(d) + lp(b''.join(lp(c) for c in certs))
          + struct.pack('<II', minsdk, maxsdk) + lp(b''))
    sg = lp(struct.pack('<I', SIG_ALG_RSA_PKCS1_SHA256) + lp(rsa_sign_sha256(key, sd)))
    signer = lp(sd) + struct.pack('<II', minsdk, maxsdk) + lp(sg) + lp(pub)
    return lp(lp(signer))


def build_block(pairs):
    body = b''.join(struct.pack('<Q', 4 + len(v)) + struct.pack('<I', i) + v
                    for i, v in pairs)
    sz = len(body) + 8 + 16
    return struct.pack('<Q', sz) + body + struct.pack('<Q', sz) + MAGIC


def eocd(n, cdsize, cdoff, comment=b''):
    return struct.pack('<IHHHHIIH', 0x06054B50, 0, 0, n, n, cdsize,
                       cdoff, len(comment)) + comment


# ---------------------------------------------------------------------------
# 9. v1（JAR）签名
# ---------------------------------------------------------------------------
def jar_line(prefix, value):
    """写一行 JAR 清单属性，按 signapk 的 70 B 规则换行（续行以单个空格开头）。

    AUDIT P1-2：原先直接拼 'Name: %s\\r\\n'，最长 92 B，违反 JAR 规范
    （每行 ≤ 72 B 含 CRLF）。官方 cn_base.apk 的 MANIFEST.MF 实测：最长行
    70 B、0 行 > 72、1,254 条续行，形如 b' on'。apksig 的 ManifestWriter
    上限是 MAX_LINE_LENGTH = 72（含 CRLF）⇒ 内容 70 B，续行首字节是空格，
    故续行正文最多 69 B。
    """
    raw = (prefix + value).encode('utf-8')
    if len(raw) <= JAR_MAX_LINE:
        return raw + b'\r\n'
    out, start, first = [], 0, True
    while start < len(raw):
        room = JAR_MAX_LINE if first else JAR_MAX_LINE - 1
        end = min(start + room, len(raw))
        if end < len(raw):
            # 不要切在 UTF-8 多字节序列中间
            e = end
            while e > start + 1 and (raw[e] & 0xC0) == 0x80:
                e -= 1
            end = e
        chunk = raw[start:end]
        out.append(chunk if first else b' ' + chunk)
        start, first = end, False
    return b''.join(c + b'\r\n' for c in out)


def build_v1(items, apk_signed=('2', '3')):
    """items: [(name, sha256_digest)] -> (MANIFEST.MF bytes, CERT.SF bytes)

    AUDIT P1-1：.SF 必须声明 X-Android-APK-Signed: 2, 3。官方 BACN.SF 与
    apksigner 产物都有；缺了 apksig 会报 JAR_SIG_NO_APK_SIG_STRIP_PROTECTION，
    且 v1-only 客户端无法得知"本包还应有 v2/v3"，剥掉签名块也照样能过。
    """
    mf = (jar_line('Manifest-Version: ', '1.0')
          + jar_line('Created-By: ', 'BA-noroot-builder') + b'\r\n')
    for name, dg in items:
        mf += (jar_line('Name: ', name)
               + jar_line('SHA-256-Digest: ', base64.b64encode(dg).decode())
               + b'\r\n')
    whole = base64.b64encode(hashlib.sha256(mf).digest()).decode()
    sf = (jar_line('Signature-Version: ', '1.0')
          + jar_line('Created-By: ', 'BA-noroot-builder')
          + jar_line('SHA-256-Digest-Manifest: ', whole))
    if apk_signed:
        # 只有真的同时产出 v2/v3 才声明；--no-v1 时根本不走这里
        sf += jar_line('X-Android-APK-Signed: ', ', '.join(apk_signed))
    sf += b'\r\n'
    return mf, sf


def jar_parse(raw):
    """解析 JAR 清单 -> (主属性 dict, [(name, attrs dict)])，用于 v1 校验。

    先按空行切段，再把每段里的续行（首字节空格）拼回上一行。
    """
    main, secs, first = {}, [], True
    for blk in raw.split(b'\r\n\r\n'):
        joined = []
        for ln in blk.split(b'\r\n'):
            if ln.startswith(b' ') and joined:
                joined[-1] += ln[1:]
            elif ln:
                joined.append(ln)
        if not joined:
            continue
        attrs = {}
        for ln in joined:
            k, sep, v = ln.partition(b': ')
            if sep:
                attrs[k.decode('utf-8', 'replace')] = v.decode('utf-8', 'replace')
        if first:
            main, first = attrs, False
        elif 'Name' in attrs:
            secs.append((attrs['Name'], attrs))
    return main, secs


# ---------------------------------------------------------------------------
# 9.5 GameMainConfig 等长替换（ServerInfoDataUrl）
#
# 算法照 work\ba\noroot\CRYPTO_MT.py（GAMEMAINCONFIG_CN.md §1 自检真值），不重新发明：
#   seed = xxHash32(UTF8(name), 0)
#   mt   = MT19937(seed)，Next() = (genrand_int32() >> 1) & 0x7FFFFFFF
#   NextBytes(n)：每 4 字节调一次 Next()，struct.pack('<I') 小端
#   create_key(name) = NextBytes(8)          # GameMainConfig = 1b 23 28 06 ad 72 c2 57
#
# 第一层：m_Script = UTF-16LE(JSON) XOR cycle8(create_key("GameMainConfig"))
# 第二层：存键 = UTF16LE(fieldName) XOR cycle8(create_key(fieldName))
#         存值 = UTF16LE(value)     XOR cycle8(create_key(fieldName))   ← 值是拿字段名当种子
#         两者各自 base64 后放进第一层 JSON
# ---------------------------------------------------------------------------
_XM = 0xFFFFFFFF
_XP1, _XP2, _XP3, _XP4, _XP5 = 2654435761, 2246822519, 3266489917, 668265263, 374761393


def _xrotl(x, r):
    x &= _XM
    return ((x << r) | (x >> (32 - r))) & _XM


def xxhash32(data, seed=0):
    n, i = len(data), 0
    if n >= 16:
        v1 = (seed + _XP1 + _XP2) & _XM
        v2 = (seed + _XP2) & _XM
        v3 = seed & _XM
        v4 = (seed - _XP1) & _XM

        def _round(v, k):
            return (_xrotl((v + (k * _XP2)) & _XM, 13) * _XP1) & _XM

        while i <= n - 16:
            v1 = _round(v1, struct.unpack_from('<I', data, i)[0])
            v2 = _round(v2, struct.unpack_from('<I', data, i + 4)[0])
            v3 = _round(v3, struct.unpack_from('<I', data, i + 8)[0])
            v4 = _round(v4, struct.unpack_from('<I', data, i + 12)[0])
            i += 16
        h = (_xrotl(v1, 1) + _xrotl(v2, 7) + _xrotl(v3, 12) + _xrotl(v4, 18)) & _XM
    else:
        h = (seed + _XP5) & _XM
    h = (h + n) & _XM
    while i + 4 <= n:
        h = (_xrotl((h + struct.unpack_from('<I', data, i)[0] * _XP3) & _XM, 17) * _XP4) & _XM
        i += 4
    while i < n:
        h = (_xrotl((h + data[i] * _XP5) & _XM, 11) * _XP1) & _XM
        i += 1
    h ^= h >> 15
    h = (h * _XP2) & _XM
    h ^= h >> 13
    h = (h * _XP3) & _XM
    h ^= h >> 16
    return h & _XM


class _MT19937:
    """BA 变体：Next() 取 (genrand_int32() >> 1) & 0x7FFFFFFF。"""

    def __init__(self, seed):
        self.mt = [0] * 624
        self.mt[0] = seed & _XM
        for i in range(1, 624):
            self.mt[i] = (1812433253 * (self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) + i) & _XM
        self.idx = 624

    def genrand(self):
        if self.idx >= 624:
            for i in range(624):
                y = (self.mt[i] & 0x80000000) | (self.mt[(i + 1) % 624] & 0x7FFFFFFF)
                v = self.mt[(i + 397) % 624] ^ (y >> 1)
                if y & 1:
                    v ^= 2567483615
                self.mt[i] = v & _XM
            self.idx = 0
        y = self.mt[self.idx]
        self.idx += 1
        y ^= y >> 11
        y ^= (y << 7) & 2636928640
        y ^= (y << 15) & 4022730752
        y ^= y >> 18
        return y & _XM

    def next32(self):
        return (self.genrand() >> 1) & 0x7FFFFFFF

    def next_bytes(self, length):
        out = bytearray(length)
        i = 0
        while i < length:
            b = struct.pack('<I', self.next32())
            for j in range(4):
                if i + j < length:
                    out[i + j] = b[j]
            i += 4
        return bytes(out)


def gmconfig_create_key(name=GMC_NAME):
    """create_key(name) -> 8 B 循环 XOR key。"""
    return _MT19937(xxhash32(name.encode('utf-8'))).next_bytes(8)


def gmconfig_xor(key8, data):
    """8 字节循环 XOR（自逆）；offset 固定 0，从 m_Script 起点开始。"""
    n = len(data)
    return bytes(a ^ b for a, b in zip(data, (key8 * (n // 8 + 1))[:n]))


def _gf_xor(name, data):
    """第二层：用字段名派生 key8 做循环 XOR（加密==解密）。"""
    k = gmconfig_create_key(name)
    return bytes(a ^ b for a, b in zip(data, (k * (len(data) // 8 + 1))[:len(data)]))


def _b64d(s):
    return base64.b64decode(s + '=' * (-len(s) % 4))


def _b64e(b):
    return base64.b64encode(b).decode('ascii')


def gmconfig_check_layout(asset, what=GMC_ENTRY):
    """硬校验 SerializedFile 布局，返回 m_Script 长度。"""
    if len(asset) != GMC_SIZE:
        die('%s：文件 %d B，必须是 %d B（m_Script 固定 %d B；变长会改 SerializedFile '
            '头部大小字段/文件大小/zip 条目，本工具不做）'
            % (what, len(asset), GMC_SIZE, GMC_SCRIPT_LEN))
    nl = struct.unpack_from('<I', asset, GMC_NAME_OFF)[0]
    nm = bytes(asset[GMC_NAME_OFF + 4:GMC_NAME_OFF + 4 + nl])
    if nl != GMC_NAMELEN or nm != GMC_NAME.encode('ascii'):
        die('%s：0x%X 处 name_len=%d / m_Name=%r，期望 14 / %r'
            % (what, GMC_NAME_OFF, nl, nm, GMC_NAME))
    if bytes(asset[GMC_NAME_OFF + 4 + nl:GMC_LEN_OFF]) != b'\x00' * (
            GMC_LEN_OFF - GMC_NAME_OFF - 4 - nl):
        die('%s：0x%X..0x%X 对齐 padding 不是全 0' % (what, GMC_NAME_OFF + 4 + nl, GMC_LEN_OFF))
    sl = struct.unpack_from('<I', asset, GMC_LEN_OFF)[0]
    if sl != GMC_SCRIPT_LEN:
        die('%s：m_Script_len@0x%X = %d，必须是 %d' % (what, GMC_LEN_OFF, sl, GMC_SCRIPT_LEN))
    if GMC_SCRIPT_OFF + sl + 2 != GMC_SIZE:
        die('%s：偏移对不上：0x%X + %d + 2 != %d' % (what, GMC_SCRIPT_OFF, sl, GMC_SIZE))
    return sl


def gmconfig_read(asset, what=GMC_ENTRY):
    """解出 6 个字段，返回 dict（含第一层 JSON、b64 键表、统计）。"""
    sl = gmconfig_check_layout(asset, what)
    k8 = gmconfig_create_key()
    body = bytes(asset[GMC_SCRIPT_OFF:GMC_SCRIPT_OFF + sl])
    try:
        plain = gmconfig_xor(k8, body).decode('utf-16-le')
    except UnicodeDecodeError as ex:
        die('%s：m_Script 解不成 UTF-16LE（key8 不对？%s）' % (what, ex))
    try:
        js = json.loads(plain)
    except ValueError as ex:
        die('%s：m_Script 解出来不是 JSON（%s）' % (what, ex))
    if not isinstance(js, dict):
        die('%s：第一层 JSON 不是对象（%r）' % (what, type(js).__name__))
    fields, keys, unknown = {}, {}, 0
    for kb, vb in js.items():
        key_ct = _b64d(kb)
        for n in GMC_FIELDS:
            # 自密钥判定式：dec(候选, 存键) == UTF16LE(候选) 是充要条件，无假阳性
            if len(n) * 2 == len(key_ct) and _gf_xor(n, key_ct) == n.encode('utf-16-le'):
                fields[n] = _gf_xor(n, _b64d(vb)).decode('utf-16-le') if vb else ''
                keys[n] = kb
                break
        else:
            unknown += 1
    return {'script_len': sl, 'cap': sl // 2, 'plain': plain, 'json': js,
            'fields': fields, 'keys': keys, 'key8': k8, 'unknown': unknown}


def gmconfig_budget(info):
    """返回 (cap, base, max_units, cur_units, doc_budget)。

    base = 第一层 JSON 里除本字段 b64 之外的字符数（固定开销）。
    max_units = 精确上限（base64 每 3 B 一组，长度不严格线性，故实算）。
    doc_budget = 文档 §9.1 的保守口径：cap - (len(plain) - len(原值))。
    """
    cap = info['cap']
    kb = info['keys'].get(GMC_URL_FIELD)
    if kb is None:
        die('解不出 %s 字段，无法计算预算' % GMC_URL_FIELD)
    cur = info['fields'].get(GMC_URL_FIELD, '')
    cur_units = len(cur.encode('utf-16-le')) // 2
    base = len(info['plain']) - len(info['json'][kb])
    max_units = 0
    for u in range(0, cap + 1):
        if base + 4 * ((2 * u + 2) // 3) <= cap:
            max_units = u
    return cap, base, max_units, cur_units, (cap - (len(info['plain']) - cur_units))


def gmconfig_budget_msg(info, value, units):
    cap, base, max_units, cur_units, doc = gmconfig_budget(info)
    need = base + 4 * ((2 * units + 2) // 3)
    plain = len(info['plain'])
    return (
        'ServerInfoDataUrl 放不下：新值 %d 字符（UTF-16 代码单元 %d）\n'
        '  预算：m_Script 固定 %d B = %d 个 UTF-16 字符（cap）\n'
        '        第一层 JSON 当前 %d 字符，余量 %d（国服 3.0.2 实测为 0）\n'
        '        其中本字段 b64 占 %d 字符，其余固定开销 %d 字符'
        '（5 个字段的 b64 + 引号/逗号/花括号）\n'
        '        值上限：%d 字符（保守口径 cap-%d）/ %d 字符（精确口径，b64 按 3 B 分组）\n'
        '        本次值 base64 后 JSON 需 %d 字符，超预算 %d\n'
        '  可行办法：① 用 http:// 代替 https://（每条 URL 省 1 字符，C 路径）\n'
        '            ② 缩短域名（http 最长 19 字符；https 最长 18 字符）\n'
        '            ③ 只保留一条 URL（["<url>"]，url ≤ 98 字符）\n'
        '            ④ 用 --gmconfig-value 直接给更短的整串'
        % (units, units, GMC_SCRIPT_LEN, cap,
           plain, cap - plain,
           plain - base, base,
           doc, plain - cur_units, max_units,
           need, need - cap))


def gmconfig_value_from_spec(spec, scheme=None):
    """把 --gmconfig-url 的输入换算成完整的 ServerInfoDataUrl 值（含 [] 的字符串）。

    1) 纯域名        bapsvr-prods-cn.com                  -> {scheme}://state-api.<d>/api/state (+qc)
    2) dispatcher    http(s)://state-api.<d>/api/state     -> 取出 <d> 重建两条（保持条数与路径）
    3) 其它 URL      https://x/si.json                     -> 单元素 ["<原样>"]
    4) 以 [ 开头                                            -> 原样当作 value
    """
    s = (spec or '').strip()
    if not s:
        die('--gmconfig-url 为空')
    if s.startswith('['):
        return s
    sch = (scheme or '').lower() or None
    if '://' not in s:
        d = s.strip('/')
        if not d or '/' in d or '?' in d:
            die('--gmconfig-url %r：既不是域名也不像 URL' % spec)
        return GMC_TMPL_PAIR.format(scheme=(sch or 'http'), domain=d)
    proto, _, rest = s.partition('://')
    use = sch or proto.lower()
    host = rest.split('/', 1)[0].split('?', 1)[0]
    for pref, cut in GMC_HOST_PREFIXES:
        if host.lower().startswith(pref):
            return GMC_TMPL_PAIR.format(scheme=use, domain=host[cut:])
    return '["%s://%s"]' % (use, rest) if sch else '["%s"]' % s


def gmconfig_domain_token(spec):
    """把 'bapsvr-prods-cn.com' / 'http://state-api.x.com/api/state' 归一成域名。"""
    s = (spec or '').strip()
    if '://' in s:
        s = s.split('://', 1)[1]
    s = s.split('/', 1)[0].split('?', 1)[0]
    for pref, cut in GMC_HOST_PREFIXES:
        if s.lower().startswith(pref):
            return s[cut:]
    return s


def gmconfig_rewrite(asset, value, allow_pad=True, what=GMC_ENTRY):
    """把 ServerInfoDataUrl 换成 value，返回 (新字节, 统计 dict)。

    等长硬约束（任一不满足直接 die，绝不产出可疑文件）：
      1) 输出仍 5,212 B
      2) m_Name / name_len / m_Script_len(1090) 与 0x1000..0x1018 头部逐字节不变
      3) 0x145A 之后尾部 padding 逐字节不变
      4) 回读 6 个字段，ServerInfoDataUrl == 新值，其余 5 个字段与源包逐字节相同
    """
    info = gmconfig_read(asset, what)
    cap = info['cap']
    plain = info['plain']
    js = info['json']
    old = info['fields'].get(GMC_URL_FIELD)
    if old is None:
        die('%s：解不出 %s' % (what, GMC_URL_FIELD))
    kb = info['keys'][GMC_URL_FIELD]
    # 第一层 JSON 必须能被原样重建，否则说明布局与文档不符，不能盲改
    rebuilt = json.dumps(js, separators=(',', ':'), ensure_ascii=False)
    if rebuilt != plain:
        die('%s：第一层 JSON 重新序列化与原文不一致（%d vs %d 字符），拒绝改写'
            % (what, len(rebuilt), len(plain)))
    try:
        raw_value = value.encode('utf-16-le')
    except UnicodeEncodeError as ex:
        die('新值无法编码成 UTF-16LE（%s）' % ex)
    units = len(raw_value) // 2
    _cap, base, _maxu, _cur, _doc = gmconfig_budget(info)
    if base + 4 * ((2 * units + 2) // 3) > cap:
        die(gmconfig_budget_msg(info, value, units))
    js2 = dict(js)
    js2[kb] = _b64e(_gf_xor(GMC_URL_FIELD, raw_value))
    if len(js2[kb]) != 4 * ((2 * units + 2) // 3):
        die('内部错误：base64 长度 %d 与预算口径不符' % len(js2[kb]))
    new_plain = json.dumps(js2, separators=(',', ':'), ensure_ascii=False)
    if len(new_plain) > cap:
        die(gmconfig_budget_msg(info, value, units))
    pad = cap - len(new_plain)
    if pad and not allow_pad:
        die('新值比原值短，需要补 %d 个尾部空格才能填满 m_Script；'
            '当前给了 --no-gmconfig-pad，拒绝构建' % pad)
    new_plain_p = new_plain + ' ' * pad
    new_body = gmconfig_xor(info['key8'], new_plain_p.encode('utf-16-le'))
    if len(new_body) != info['script_len']:
        die('内部错误：密文 %d B != m_Script %d B' % (len(new_body), info['script_len']))

    out = bytes(asset[:GMC_SCRIPT_OFF]) + new_body + bytes(asset[GMC_SCRIPT_OFF + info['script_len']:])

    # ---- 等长硬校验 ----
    if len(out) != GMC_SIZE:
        die('等长校验失败：输出 %d B != %d B' % (len(out), GMC_SIZE))
    if out[:GMC_SCRIPT_OFF] != bytes(asset[:GMC_SCRIPT_OFF]):
        die('等长校验失败：0x0..0x%X 头部/长度字段被改动' % GMC_SCRIPT_OFF)
    if out[GMC_SCRIPT_OFF + info['script_len']:] != \
            bytes(asset[GMC_SCRIPT_OFF + info['script_len']:]):
        die('等长校验失败：尾部 padding 被改动')
    chk = gmconfig_read(out, what)
    if chk['script_len'] != GMC_SCRIPT_LEN:
        die('等长校验失败：回读 m_Script_len=%d' % chk['script_len'])
    if chk['fields'].get(GMC_URL_FIELD) != value:
        die('回读校验失败：ServerInfoDataUrl = %r，期望 %r'
            % (chk['fields'].get(GMC_URL_FIELD), value))
    for f in GMC_FIELDS:
        if f == GMC_URL_FIELD:
            continue
        if chk['fields'].get(f) != info['fields'].get(f):
            die('回读校验失败：字段 %s 被误改（%r -> %r）'
                % (f, info['fields'].get(f), chk['fields'].get(f)))
        if chk['json'][chk['keys'][f]] != info['json'][info['keys'][f]]:
            die('回读校验失败：字段 %s 的密文 b64 变了' % f)
    old_body = bytes(asset[GMC_SCRIPT_OFF:GMC_SCRIPT_OFF + info['script_len']])
    diff = [i for i in range(info['script_len']) if new_body[i] != old_body[i]]
    return out, {'old': old, 'value': value, 'units': units, 'pad': pad,
                 'json_len': len(new_plain), 'diff': len(diff),
                 'diff_range': (min(diff), max(diff)) if diff else (0, 0),
                 'cap': cap, 'base': base, 'budget': gmconfig_budget(info)}


def gmconfig_selfcheck(apk_path, expect_value=None, baseline=None, tag='产物 APK'):
    """从产物 APK 里把 GameMainConfig 读回来、解密、逐字段核对。返回 info。"""
    import zipfile
    zf = zipfile.ZipFile(apk_path)
    try:
        names = zf.namelist()
        if GMC_ENTRY not in names:
            die('%s 里没有 %s' % (tag, GMC_ENTRY))
        zi = zf.getinfo(GMC_ENTRY)
        data = zf.read(GMC_ENTRY)
    finally:
        zf.close()
    if zi.file_size != GMC_SIZE or len(data) != GMC_SIZE:
        die('%s 里 %s 是 %d B（zip 声明 %d），必须是 %d B'
            % (tag, GMC_ENTRY, len(data), zi.file_size, GMC_SIZE))
    info = gmconfig_read(data, '%s/%s' % (tag, GMC_ENTRY))
    if len(info['fields']) != len(GMC_FIELDS):
        miss = [f for f in GMC_FIELDS if f not in info['fields']]
        die('%s：只解出 %d/%d 个字段，缺 %s'
            % (tag, len(info['fields']), len(GMC_FIELDS), miss))
    if expect_value is not None and info['fields'][GMC_URL_FIELD] != expect_value:
        die('%s：ServerInfoDataUrl = %r，期望 %r'
            % (tag, info['fields'][GMC_URL_FIELD], expect_value))
    if baseline is not None:
        for f in GMC_FIELDS:
            if f == GMC_URL_FIELD:
                continue
            if baseline['fields'].get(f) != info['fields'].get(f):
                die('%s：字段 %s 与源包不同（%r -> %r）'
                    % (tag, f, baseline['fields'].get(f), info['fields'].get(f)))
            if baseline['json'][baseline['keys'][f]] != info['json'][info['keys'][f]]:
                die('%s：字段 %s 的密文 b64 与源包不同' % (tag, f))
    log('    %s: %d B, m_Script=%d B, 字段 %d/%d'
        % (os.path.basename(apk_path), len(data), info['script_len'],
           len(info['fields']), len(GMC_FIELDS)))
    for f in GMC_FIELDS:
        v = info['fields'].get(f, '<缺失>')
        log('      %-18s = %r' % (f, v))
    return info


# ---------------------------------------------------------------------------
# 10. 构建
# ---------------------------------------------------------------------------
def patch_sdk_url(data, new):
    txt = data.decode('utf-8')
    m = re.search(r'("sdk_url"\s*:\s*")([^"\\]*)(")', txt)
    if not m:
        die('SDKConfigSettings.json 里没有 sdk_url')
    old = m.group(2)
    out = txt[:m.start(2)] + new + txt[m.end(2):]
    if json.loads(out).get('sdk_url') != new:
        die('sdk_url 校验失败')
    return out.encode('utf-8'), old


def normalize_ca(path):
    raw = open(path, 'rb').read()
    if b'-----BEGIN' in raw:
        c = [d for (l, d) in pem_blocks(raw.decode('utf-8', 'replace'))
             if l in ('CERTIFICATE', 'TRUSTED CERTIFICATE')]
        if not c:
            die('%s 里没有 CERTIFICATE' % path)
        if len(c) > 1:
            log('[!] %s 含 %d 张证书，只取第一张' % (path, len(c)))
        der = c[0]
    else:
        der = raw
    if der_read_tlv(der, 0)[0] != 0x30:
        die('%s 不是 X.509 证书' % path)
    return der, hashlib.sha256(der).hexdigest().upper()


def do_build(src_path, out_path, sdk_url, ca_path, ca_mode, key, cert,
             v1_on=True, arsc_first=True, align_mode='raw',
             gmconfig_value=None, gmconfig_pad=True, asset_replace=None):
    assert_key_pair(key, cert)          # AUDIT P1-4：私钥/证书必须配对
    src = SrcZip(src_path)
    pub = rsa_public_der(key)
    log('[*] 签名证书 SHA-256 = %s' % hashlib.sha256(cert).hexdigest().upper())

    ca_der = None
    if ca_path:
        ca_der, ca_sha = normalize_ca(ca_path)
        log('[*] 内置 CA: %s  SHA-256=%s' % (ca_path, ca_sha))
        if ca_mode not in ('both', 'bundled'):
            log('[!] 给了 --ca 但 --ca-mode=%s，按 both 处理' % ca_mode)
            ca_mode = 'both'
    if ca_mode in ('both', 'bundled') and ca_der is None:
        die('--ca-mode %s 必须配 --ca' % ca_mode)

    nsc = build_nsc_axml(ca_mode)
    rep = {NSC_ENTRY: nsc}
    log('[1] %s: %d B -> %d B  (ca_mode=%s)'
        % (NSC_ENTRY, src.by_name[NSC_ENTRY]['usize'], len(nsc), ca_mode))
    if ca_mode in ('both', 'bundled'):
        if not src.has(SPARE_RAW_ENTRY):
            die('没有 %s 可用作 CA 槽' % SPARE_RAW_ENTRY)
        rep[SPARE_RAW_ENTRY] = ca_der
        log('[4] %s: %d B -> %d B  (内置 CA, 牺牲 zxing 提示音)'
            % (SPARE_RAW_ENTRY, src.by_name[SPARE_RAW_ENTRY]['usize'], len(ca_der)))
    if sdk_url:
        j, old = patch_sdk_url(src.read(SDKCFG_ENTRY), sdk_url)
        rep[SDKCFG_ENTRY] = j
        log('[2] %s: sdk_url %r -> %r' % (SDKCFG_ENTRY, old, sdk_url))
    else:
        log('[2] 跳过（未给 --sdk-url）')

    # ---- [2b] GameMainConfig / ServerInfoDataUrl（state 入口，等长替换）----
    gm_orig = None            # 源包原始 asset（自检基线）
    gm_expect = None          # 期望的新 ServerInfoDataUrl（自检判据）
    gmstat = None
    if gmconfig_value:
        if not src.has(GMC_ENTRY):
            die('源包里没有 %s，改不了 ServerInfoDataUrl（不是国服 3.0.2？）' % GMC_ENTRY)
        gm_orig = src.read(GMC_ENTRY)
        new_gm, gmstat = gmconfig_rewrite(gm_orig, gmconfig_value, gmconfig_pad)
        rep[GMC_ENTRY] = new_gm
        gm_expect = gmconfig_value
        log('[2b] %s: %d B -> %d B  (等长 OK, 密文差异 %d B, 补 %d 空格)'
            % (GMC_ENTRY, len(gm_orig), len(new_gm), gmstat['diff'], gmstat['pad']))
        log('[2b] ServerInfoDataUrl:')
        log('[2b]   old = %r  (%d 字符)' % (gmstat['old'], len(gmstat['old'])))
        log('[2b]   new = %r  (%d 字符)' % (gmstat['value'], gmstat['units']))
        log('[2b] 预算: cap=%d 字符, 固定开销=%d, 上限=%d(保守)/%d(精确), '
            'layer1 JSON=%d/%d'
            % (gmstat['cap'], gmstat['base'], gmstat['budget'][4],
               gmstat['budget'][2], gmstat['json_len'], gmstat['cap']))
    elif src.has(GMC_ENTRY):
        log('[2b] 跳过 GameMainConfig（未给 --gmconfig-url / --asset-replace）')
    else:
        log('[2b] 源包里没有 %s（跳过 GameMainConfig）' % GMC_ENTRY)

    # ---- [2c] 通用 asset 替换（逃生口）----
    if asset_replace:
        for name, path in asset_replace.items():
            if name == GMC_ENTRY and gmconfig_value:
                die('--gmconfig-url 与 --asset-replace %s 冲突，只能给一个' % GMC_ENTRY)
            if not src.has(name):
                die('源包里没有条目 %s（--asset-replace）' % name)
            if not os.path.isfile(path):
                die('--asset-replace 本地文件不存在：%s' % path)
            data = open(path, 'rb').read()
            if name == GMC_ENTRY:
                # 已知尺寸的 asset：必须过一遍结构 + 字段自检
                info_rep = gmconfig_read(data, path)
                if len(info_rep['fields']) != len(GMC_FIELDS):
                    die('%s：只解出 %d/%d 个字段（缺 %s）'
                        % (path, len(info_rep['fields']), len(GMC_FIELDS),
                           [f for f in GMC_FIELDS if f not in info_rep['fields']]))
                gm_orig = src.read(name)
                gm_expect = info_rep['fields'].get(GMC_URL_FIELD)
                log('[2c] %s 的结构与字段自检通过：%s 里 ServerInfoDataUrl = %r'
                    % (name, os.path.basename(path), gm_expect))
            rep[name] = data
            log('[2c] %s: %d B -> %d B  (--asset-replace %s)'
                % (name, src.by_name[name]['usize'], len(data), path))

    deleted = [n for n in TPINFO_ENTRIES if src.has(n)]
    for n in deleted:
        log('[3] 删除 %s (%d B)' % (n, src.by_name[n]['usize']))

    # 旧 v1 签名文件（原厂 BACN.SF/BACN.RSA/MANIFEST.MF）必须剔除，
    # 否则我们重新生成的同名条目会造成 zip 重名 —— Android 直接拒装
    old_sig = [e['name'] for e in src.entries if is_old_signature(e['name'])]
    for n in old_sig:
        log('[6] 剔除旧签名 %s (%d B)' % (n, src.by_name[n]['usize']))

    drop = set(deleted) | set(old_sig)
    order = [e['name'] for e in src.entries if e['name'] not in drop]
    if arsc_first and 'resources.arsc' in order:
        order.remove('resources.arsc')
        order.insert(0, 'resources.arsc')
        log('[5] resources.arsc 置第 1 条（STORED + 4 字节对齐, align_mode=%s）'
            % align_mode)

    tmp = out_path + '.tmp'
    zw = ZipWriter(tmp, align_mode)
    v1_items = []
    log('[*] 写入 %d 条目 -> %s' % (len(order), tmp))
    t0 = time.time()
    for i, name in enumerate(order):
        if i and i % 8000 == 0:
            log('    %6d/%d  %s' % (i, len(order), human(zw.pos)))
        e = src.by_name[name]
        if name in rep:
            data = rep[name]
            if v1_on:
                v1_items.append((name, hashlib.sha256(data).digest()))
            zw.add(name, 0, zlib.crc32(data) & 0xFFFFFFFF, len(data), len(data),
                   e['dt'], [data])
        else:
            h = hashlib.sha256() if v1_on else None
            zw.add(name, e['method'], e['crc'], e['csize'], e['usize'], e['dt'],
                   src.chunks(name), h)
            if v1_on:
                v1_items.append((name, h.digest()))

    if v1_on:
        mf, sf = build_v1(v1_items)
        p7 = pkcs7_signed_data(key, cert, sf)
        for nm, blob in (('META-INF/MANIFEST.MF', mf), ('META-INF/CERT.SF', sf),
                         ('META-INF/CERT.RSA', p7)):
            zw.add(nm, 0, zlib.crc32(blob) & 0xFFFFFFFF, len(blob), len(blob),
                   (2026, 11, 16, 0, 0, 0), [blob])
        log('[6] v1: MANIFEST.MF %d B / CERT.SF %d B / CERT.RSA %d B'
            % (len(mf), len(sf), len(p7)))

    entries_size = zw.pos
    cd = b''.join(zw.cd)
    n = len(zw.cd)
    zw.close()

    if entries_size + len(cd) + 4096 > MAX32:
        die('输出将超过 2^31-1，需要 Zip64，本工具不支持', 2)

    eo_digest = eocd(n, len(cd), entries_size, b'')
    digest = zw.chunk1.digest([cd, eo_digest])
    log('[*] 内容摘要 %s' % digest.hex())

    v2 = build_v2_signer(digest, [cert], pub, key)
    v3 = build_v3_signer(digest, [cert], pub, key, MIN_SDK, MAX32)
    block = build_block([(V2_BLOCK_ID, v2), (V3_BLOCK_ID, v3)])

    with open(tmp, 'r+b') as f:
        f.seek(entries_size)
        f.write(block)
        f.write(cd)
        f.write(eocd(n, len(cd), entries_size + len(block), b''))
        f.truncate()
    os.replace(tmp, out_path)
    log('[6] v2 %d B + v3 %d B，签名块共 %d B @%d'
        % (len(v2), len(v3), len(block), entries_size))
    log('[*] 写完 %.1fs，%s' % (time.time() - t0, human(os.path.getsize(out_path))))
    src.close()

    # ---- [7] 从产物 APK 回读 GameMainConfig 自检（要求 3）----
    if GMC_ENTRY in rep:
        log('[7] 自检：从产物 APK 回读 GameMainConfig（解密 + 6 字段比对）')
        baseline = gmconfig_read(gm_orig, '源包 %s' % GMC_ENTRY) if gm_orig else None
        info = gmconfig_selfcheck(out_path, expect_value=gm_expect, baseline=baseline)
        if baseline is not None:
            log('[7] 其余 5 字段与源包逐字节相同：OK（值 + 密文 b64 双重比对）')
        if gmstat:
            log('[7] 等长：文件 %d B / m_Script %d B / 密文差异 %d B'
                % (GMC_SIZE, info['script_len'], gmstat['diff']))
    return nsc


# ---------------------------------------------------------------------------
# 11. 校验（独立实现，含 RSA 验签）
# ---------------------------------------------------------------------------
def parse_pkcs7(der):
    """解析 META-INF/*.RSA（PKCS#7 detached SignedData），返回 signer/cert 摘要。"""
    _, vo, vl, _ = der_read_tlv(der, 0)              # ContentInfo SEQUENCE
    ci = der_children(der, vo, vo + vl)
    if len(ci) < 2 or ci[0][0] != 0x06 or ci[1][0] != 0xA0:
        raise ValueError('不是 PKCS#7 ContentInfo')
    sd0 = der_children(der, ci[1][1], ci[1][1] + ci[1][2])
    if not sd0 or sd0[0][0] != 0x30:
        raise ValueError('SignedData 缺失')
    sd = der_children(der, sd0[0][1], sd0[0][1] + sd0[0][2])
    certs, signer = [], None
    for t, a, l, s0, s1 in sd:
        if t == 0xA0:
            for ct, ca, cl, c0, c1 in der_children(der, a, a + l):
                if ct == 0x30:
                    certs.append(der[c0:c1])
        elif t == 0x31:
            kids = der_children(der, a, a + l)
            if kids:
                signer = der[kids[-1][3]:kids[-1][4]]     # 最后一个 SignerInfo
    if signer is None:
        raise ValueError('SignerInfo 缺失')
    _t, svo, svl, _s = der_read_tlv(signer, 0)
    si = der_children(signer, svo, svo + svl)
    sig_oct = None
    signed_attrs = None
    algs = []
    for x in si:
        if x[0] == 0x04 and sig_oct is None:
            sig_oct = signer[x[1]:x[1] + x[2]]
        elif x[0] == 0xA0 and signed_attrs is None:
            signed_attrs = signer[x[3]:x[4]]     # [0] IMPLICIT SignedAttributes
        elif x[0] == 0x30:
            kids = der_children(signer, x[1], x[1] + x[2])
            if kids and kids[0][0] == 0x06:      # AlgorithmIdentifier
                algs.append(signer[x[3]:x[4]])
    if sig_oct is None:
        raise ValueError('encryptedDigest 缺失')
    return {'certs': certs, 'signature': sig_oct, 'signed_attrs': signed_attrs,
            'digest_alg': algs[0] if algs else None,
            'sig_alg': algs[1] if len(algs) > 1 else None}


def _p7_message_digest(signed_attrs):
    """从 SignedAttributes 里取 messageDigest 属性值（OCTET STRING）。"""
    _t, vo, vl, _s = der_read_tlv(signed_attrs, 0)
    for t, a, l, s0, s1 in der_children(signed_attrs, vo, vo + vl):
        if t != 0x30:
            continue
        kids = der_children(signed_attrs, a, a + l)
        if not kids or kids[0][0] != 0x06:
            continue
        oid = signed_attrs[kids[0][3]:kids[0][4]]
        if oid == der_oid(OID_P7_MESSAGEDIGEST) and len(kids) > 1:
            vals = der_children(signed_attrs, kids[1][1], kids[1][1] + kids[1][2])
            if vals and vals[0][0] == 0x04:
                return signed_attrs[vals[0][1]:vals[0][1] + vals[0][2]]
    return None


def verify_pkcs7(sig_der, data):
    """用 .RSA 里自带证书的公钥验 detached 签名。返回 (ok, why, cert_der)。"""
    try:
        info = parse_pkcs7(sig_der)
    except Exception as ex:
        return False, 'PKCS#7 解析失败 %r' % (ex,), None
    if not info['certs']:
        return False, 'PKCS#7 里没有证书', None
    cert = info['certs'][0]
    if info['digest_alg'] is not None:
        try:
            _t, a, l, _s, _n = der_read_tlv(info['digest_alg'], 0)
            kids = der_children(info['digest_alg'], a, a + l)
            oid = info['digest_alg'][kids[0][3]:kids[0][4]]
            if kids[0][0] == 0x06 and oid != der_oid(OID_SHA256):
                return False, 'digestAlgorithm 不是 SHA-256', cert
        except Exception:
            pass
    try:
        n, e = cert_pub_n_e(cert)
    except Exception as ex:
        return False, '证书公钥解析失败 %r' % (ex,), cert
    if info['signed_attrs'] is not None:
        # RFC 2315：签名覆盖 signedAttrs 的 DER（tag 换成 SET 0x31），
        # 内容摘要以 messageDigest 属性形式参与签名
        want = _p7_message_digest(info['signed_attrs'])
        got = hashlib.sha256(data).digest()
        if want is not None and want != got:
            return False, 'signedAttrs.messageDigest 与 .SF 不一致', cert
        to_sign = b'\x31' + info['signed_attrs'][1:]
        good, why = rsa_verify_sha256(n, e, to_sign, info['signature'])
        return good, why, cert
    good, why = rsa_verify_sha256(n, e, data, info['signature'])
    return good, why, cert


def verify_v1(zf, require=True, expect_cert_sha=None):
    """AUDIT P1-3：校验 JAR(v1) 签名 —— 逐条摘要 / 整份摘要 / PKCS#7 / 剥离保护。"""
    ok = True
    names = zf.namelist()
    if 'META-INF/MANIFEST.MF' not in names:
        log('  v1: 没有 META-INF/MANIFEST.MF（%s）'
            % ('--no-v1 构建？' if not require else '缺失'))
        return not require
    mf_raw = zf.read('META-INF/MANIFEST.MF')
    _main, secs = jar_parse(mf_raw)
    log('  v1: MANIFEST.MF %d B, %d 个 Name 段' % (len(mf_raw), len(secs)))
    lens = [len(x) for x in mf_raw.split(b'\r\n')]
    over = sum(1 for x in lens if x > 72)
    log('  v1: 最长行 %d B, 超 72 B 的行 %d 个%s'
        % (max(lens) if lens else 0, over, '（OK）' if over == 0 else '（违反 JAR 规范）'))
    if over:
        ok = False
    bad, missing, checked = [], 0, 0
    for nm, attrs in secs:
        dg = attrs.get('SHA-256-Digest')
        if nm not in names:
            missing += 1
            bad.append((nm, '条目不存在'))
            continue
        if dg is None:
            bad.append((nm, '段里没有 SHA-256-Digest'))
            continue
        got = base64.b64encode(hashlib.sha256(zf.read(nm)).digest()).decode()
        checked += 1
        if got != dg:
            bad.append((nm, '摘要不符'))
        if checked % 20000 == 0:
            log('      ...已验 %d 条' % checked)
    log('  v1: 逐条摘要 %d 条, 不符 %d, 条目缺失 %d %s'
        % (checked, len([b for b in bad if b[1] == '摘要不符']), missing,
           'OK' if not bad else 'FAIL ' + repr(bad[:3])))
    ok = ok and not bad
    sf_names = [n for n in names
                if n.startswith('META-INF/') and n.upper().endswith('.SF')]
    if not sf_names:
        log('  v1: 没有 .SF')
        return False
    sf_raw = zf.read(sf_names[0])
    sf_main, sf_secs = jar_parse(sf_raw)
    whole = base64.b64encode(hashlib.sha256(mf_raw).digest()).decode()
    got = sf_main.get('SHA-256-Digest-Manifest')
    same = (got == whole)
    log('  v1: %s SHA-256-Digest-Manifest %s（%d 个逐条段）'
        % (sf_names[0], 'OK' if same else 'FAIL', len(sf_secs)))
    ok = ok and same
    xa = sf_main.get('X-Android-APK-Signed')
    log('  v1: X-Android-APK-Signed = %r%s' % (xa, '' if xa else '  ← 缺剥离保护'))
    if require and not xa:
        ok = False
    sig_names = [n for n in names if n.startswith('META-INF/')
                 and n.upper().endswith(('.RSA', '.DSA', '.EC'))]
    if not sig_names:
        log('  v1: 没有 .RSA/.DSA/.EC（无签名块）')
        return False
    good, why, cert = verify_pkcs7(zf.read(sig_names[0]), sf_raw)
    log('  v1: %s 对 .SF 的 PKCS#7 验签 %s'
        % (sig_names[0], 'OK' if good else 'FAIL ' + why))
    ok = ok and good
    if cert is not None:
        log('  v1: 签名者证书 SHA-256 = %s'
            % hashlib.sha256(cert).hexdigest().upper())
        try:
            log('  v1: 签名者证书 SPKI %d B' % len(cert_spki(cert)))
        except Exception:
            pass
        if expect_cert_sha:
            same_cert = hashlib.sha256(cert).hexdigest().upper() == expect_cert_sha
            log('  v1 与 v2/v3 证书一致: %s' % ('OK' if same_cert else 'FAIL'))
            ok = ok and same_cert
    return ok


def verify(path, require_v1=True, expect_gmconfig=None):
    import zipfile
    size = os.path.getsize(path)
    log('[*] 校验 %s (%s)' % (path, human(size)))
    ok = True
    with open(path, 'rb') as f:
        f.seek(max(0, size - 70000))
        tail = f.read()
        i = tail.rfind(b'PK\x05\x06')
        if i < 0:
            log('  [!] 无 EOCD')
            return False
        _s, _d1, _d2, n1, n2, cdsize, cdoff, clen = struct.unpack('<IHHHHIIH',
                                                                   tail[i:i + 22])
        log('  EOCD entries=%d cd_size=%d cd_offset=%d comment=%d'
            % (n1, cdsize, cdoff, clen))
        if size - (i + len(tail) - len(tail) + len(tail)) != size:
            pass
        blk_start, bsz, v2, v3 = -1, 0, None, None
        if cdoff >= 32:
            f.seek(cdoff - 24)
            t = f.read(24)
            if t[8:] == MAGIC:
                bsz = struct.unpack('<Q', t[:8])[0]
                blk_start = cdoff - bsz - 8
                f.seek(blk_start)
                if struct.unpack('<Q', f.read(8))[0] == bsz:
                    f.seek(blk_start + 8)
                    body = f.read(bsz - 24)
                    p = 0
                    while p < len(body):
                        pl = struct.unpack('<Q', body[p:p + 8])[0]
                        pid = struct.unpack('<I', body[p + 8:p + 12])[0]
                        v = body[p + 12:p + 8 + pl]
                        if pid == V2_BLOCK_ID:
                            v2 = v
                        elif pid == V3_BLOCK_ID:
                            v3 = v
                        p += 8 + pl
        log('  APK Signing Block: %s'
            % ('OK @%d (%d B)' % (blk_start, bsz) if blk_start >= 0 else '缺失'))
        if blk_start < 0:
            return False
        ch = ChunkHasher()
        f.seek(0)
        left = blk_start
        while left:
            b = f.read(min(CHUNK, left))
            if not b:
                break
            ch.update(b)
            left -= len(b)
        f.seek(blk_start + bsz + 8)
        cd = f.read(cdsize)
        eo = eocd(n1, cdsize, blk_start, b'')
        digest = ch.digest([cd, eo])
        log('  content digest = %s' % digest.hex())
        for label, val, is3 in (('v2', v2, False), ('v3', v3, True)):
            if val is None:
                log('  %s: 缺失' % label)
                ok = False
                continue
            good, why = _verify_signer(val, digest, is3)
            log('  %s: %s' % (label, 'OK' if good else 'FAIL ' + why))
            ok = ok and good
    zf = zipfile.ZipFile(path)
    bad = zf.testzip()
    log('  zip 完整性: %s' % ('OK' if bad is None else '坏条目 %s' % bad))
    ok = ok and bad is None
    # AUDIT P1-3：v1（JAR）签名必须一起验，否则"全绿"对 v1 没有保证
    v2_cert_sha = None
    if v2 is not None:
        try:
            cs = _signer_certs(v2, False)
            if cs:
                v2_cert_sha = hashlib.sha256(cs[0]).hexdigest().upper()
                log('  v2/v3 签名者证书 SHA-256 = %s' % v2_cert_sha)
        except Exception as ex:
            log('  [!] 取 v2 证书失败 %r' % (ex,))
    try:
        v1ok = verify_v1(zf, require=require_v1, expect_cert_sha=v2_cert_sha)
    except Exception as ex:
        log('  v1: 校验异常 %r' % (ex,))
        v1ok = False
    log('  v1 结论: %s' % ('OK' if v1ok else 'FAIL'))
    ok = ok and v1ok
    with open(path, 'rb') as f:
        mis = []
        for zi in zf.infolist():
            if zi.compress_type != 0:
                continue
            f.seek(zi.header_offset)
            sig, _v, _fl, _m, _t, _d, _c, _cs, _us, nl, el = \
                struct.unpack('<IHHHHHIIIHH', f.read(30))
            off = zi.header_offset + 30 + nl + el
            if off % 4:
                mis.append((zi.filename, off % 4))
        log('  STORED 4 字节对齐: %s'
            % ('OK' if not mis else '错位 %d 条 %s' % (len(mis), mis[:3])))
        ok = ok and not mis
    names = zf.namelist()
    from collections import Counter
    _c = Counter(names)
    dups = [k for k, v in _c.items() if v > 1]
    log('  重复条目: %s' % (dups[:5] if dups else '无（OK）'))
    ok = ok and not dups
    stale = [n for n in names if is_old_signature(n) and False]
    log('  resources.arsc: 第 %d 条, STORED=%s'
        % (names.index('resources.arsc') + 1,
           zf.getinfo('resources.arsc').compress_type == 0))
    left_tp = [n for n in names if n in TPINFO_ENTRIES]
    log('  __tpinfo 残留: %s' % (left_tp if left_tp else '无（OK）'))
    ok = ok and not left_tp
    if GMC_ENTRY in names:
        try:
            g = gmconfig_read(zf.read(GMC_ENTRY), 'GameMainConfig@%s' % os.path.basename(path))
            log('  GameMainConfig: %d B, m_Script=%d B, 字段 %d/%d'
                % (GMC_SIZE, g['script_len'], len(g['fields']), len(GMC_FIELDS)))
            for fn in GMC_FIELDS:
                log('    %-18s = %r' % (fn, g['fields'].get(fn, '<缺失>')))
            if len(g['fields']) != len(GMC_FIELDS):
                log('  [!] GameMainConfig 字段不全')
                ok = False
            if expect_gmconfig is not None:
                same = g['fields'].get(GMC_URL_FIELD) == expect_gmconfig
                log('  GameMainConfig: ServerInfoDataUrl == 期望值: %s'
                    % ('OK' if same else 'FAIL（%r != %r）'
                       % (g['fields'].get(GMC_URL_FIELD), expect_gmconfig)))
                ok = ok and same
        except SystemExit:
            raise
        except Exception as ex:
            log('  [!] GameMainConfig 解析失败 %r' % (ex,))
            ok = False
    else:
        log('  GameMainConfig: 源包里没有（跳过）')
    if 'res/Dk.xml' in names:
        ev = axml_parse(zf.read('res/Dk.xml'))
        log('  res/Dk.xml 解析：')
        for line in axml_text(ev).splitlines():
            log('    ' + line)
        txt = axml_text(ev)
        if 'src="user"' not in txt:
            log('  [!] 没有 src="user"，用户 CA 不会被信任')
    return ok


def _read_lp(b, p):
    n = struct.unpack('<I', b[p:p + 4])[0]
    return b[p + 4:p + 4 + n], p + 4 + n


def _signer_certs(seq, is3):
    """从 v2/v3 签名块的 signer 里取出证书 DER 列表。"""
    signers, _ = _read_lp(seq, 0)
    signer, _ = _read_lp(signers, 0)
    sd, p = _read_lp(signer, 0)
    if is3:
        p += 8
    _sigs, p = _read_lp(signer, p)
    _pub, p = _read_lp(signer, p)
    _ds, p2 = _read_lp(sd, 0)                 # digests 序列
    certs_seq, _ = _read_lp(sd, p2)           # 证书序列（每个元素再 lp）
    out, q = [], 0
    while q < len(certs_seq):
        c, q = _read_lp(certs_seq, q)
        out.append(c)
    return out


def _verify_signer(seq, digest, is3):
    try:
        signers, _ = _read_lp(seq, 0)      # 签名者序列
        signer, _ = _read_lp(signers, 0)   # 第一个 signer
        sd, p = _read_lp(signer, 0)
        if is3:
            p += 8
        sigs, p = _read_lp(signer, p)
        pub, p = _read_lp(signer, p)
        found = False
        ds, _q = _read_lp(sd, 0)
        k = 0
        while k < len(ds):
            one, k = _read_lp(ds, k)
            alg = struct.unpack('<I', one[:4])[0]
            dg, _x = _read_lp(one, 4)
            if alg == SIG_ALG_RSA_PKCS1_SHA256 and dg == digest:
                found = True
        if not found:
            return False, '内容摘要不匹配'
        n, e = _parse_spki(pub)
        q = 0
        while q < len(sigs):
            one, q = _read_lp(sigs, q)
            alg = struct.unpack('<I', one[:4])[0]
            sg, _y = _read_lp(one, 4)
            if alg != SIG_ALG_RSA_PKCS1_SHA256:
                continue
            good, why = rsa_verify_sha256(n, e, sd, sg)
            if not good:
                return False, why
        return True, 'ok'
    except Exception as ex:
        return False, '解析异常 %r' % (ex,)


def _parse_spki(der):
    _, vo, vl, _ = der_read_tlv(der, 0)
    bits = der_children(der, vo, vo + vl)[1]
    raw = der[bits[1] + 1:bits[1] + bits[2]]
    _, v2, l2, _ = der_read_tlv(raw, 0)
    k = der_children(raw, v2, v2 + l2)
    return (int.from_bytes(raw[k[0][1]:k[0][1] + k[0][2]], 'big'),
            int.from_bytes(raw[k[1][1]:k[1][1] + k[1][2]], 'big'))


# ---------------------------------------------------------------------------
# 12. 密钥
# ---------------------------------------------------------------------------
def _openssl(argv):
    exe = shutil.which('openssl')
    if not exe:
        return None
    try:
        return subprocess.run([exe] + argv, capture_output=True)
    except Exception:
        return None


def gen_keystore(path, password='<REDACTED_DB_CREDENTIAL>', alias='ba', bits=2048):
    log('[*] 生成 RSA-%d 签名密钥' % bits)
    key = rsa_generate(bits, progress=log)
    cert = build_self_signed_cert(key, cn=alias)
    base = os.path.splitext(os.path.abspath(path))[0]
    os.makedirs(os.path.dirname(base) or '.', exist_ok=True)
    kp, cp = base + '.key.pem', base + '.cert.pem'
    open(kp, 'w', encoding='utf-8').write(rsa_private_pem(key))
    open(cp, 'w', encoding='utf-8').write(pem_wrap('CERTIFICATE', cert))
    r = _openssl(['pkcs12', '-export', '-inkey', kp, '-in', cp, '-name', alias,
                  '-out', path, '-passout', 'pass:' + password])
    p12 = bool(r and r.returncode == 0)
    if not p12:
        log('[!] openssl 不可用/失败：未生成 PKCS#12；'
            '构建请改用 --key-pem %s --cert-pem %s' % (kp, cp))
    log('[+] 完成')
    log('      keystore : %s  (%s)' % (path, 'PKCS#12' if p12 else '未生成'))
    log('      alias    : %s    pass: %s' % (alias, password))
    log('      key.pem  : %s' % kp)
    log('      cert.pem : %s' % cp)
    log('      cert SHA-256 = %s' % hashlib.sha256(cert).hexdigest().upper())
    assert_key_pair(key, cert, 'gen-keystore: ')     # 顺带验证证书里嵌的公钥
    return key, cert


def load_key(keystore, password, key_pem, cert_pem):
    if key_pem:
        if not cert_pem:
            die('--key-pem 需要 --cert-pem')
        key = rsa_key_from_pem(open(key_pem, encoding='utf-8').read())
        c = [d for (l, d) in pem_blocks(open(cert_pem, encoding='utf-8').read())
             if l == 'CERTIFICATE']
        if not c:
            die('%s 里没有 CERTIFICATE' % cert_pem)
        cert = c[0]
        assert_key_pair(key, cert, '--key-pem %s / --cert-pem %s: '
                        % (os.path.basename(key_pem), os.path.basename(cert_pem)))
        return key, cert
    if not os.path.exists(keystore):
        die('keystore 不存在：%s（先跑 --gen-keystore）' % keystore)
    if open(keystore, 'rb').read(4) == b'\xfe\xed\xfe\xed':
        die('%s 是 JKS。纯 Python 不解析 JKS；用 keytool 转 PKCS#12，或 --key-pem/--cert-pem'
            % keystore)
    tmp = tempfile.mkdtemp()
    try:
        out = os.path.join(tmp, 'ks.pem')
        for extra in ([], ['-legacy']):
            r = _openssl(['pkcs12'] + extra + ['-in', keystore, '-nodes',
                                              '-passin', 'pass:' + password, '-out', out])
            if r and r.returncode == 0:
                break
        else:
            die('openssl 打不开 %s（密码错？或需要 -legacy）' % keystore)
        txt = open(out, encoding='utf-8', errors='replace').read()
        key = cert = None
        for label, der in pem_blocks(txt):
            if label in ('RSA PRIVATE KEY', 'PRIVATE KEY') and key is None:
                key = parse_rsa_der(der)
            elif label == 'CERTIFICATE' and cert is None:
                cert = der
        if not key or not cert:
            die('%s 里没同时找到私钥和证书' % keystore)
        assert_key_pair(key, cert, '%s: ' % keystore)
        return key, cert
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 13. 自检
# ---------------------------------------------------------------------------
def gmconfig_synth(value=None):
    """造一个结构合法的 5,212 B GameMainConfig（不依赖 2 GB 源包的自检用）。

    字段与国服 3.0.2 实测一致；value 默认是官方两条 https dispatcher。
    """
    if value is None:
        value = GMC_TMPL_PAIR.format(scheme='https', domain='bluearchive-cn.com')
    fields = {'SkipTutorial': 'False', 'ServerInfoDataUrl': value,
              'ServerName': 'prod', 'VersionCode': '73',
              'PlatformID': '1', 'ChannelID': '1'}
    js = {}
    for f in GMC_FIELDS:
        js[_b64e(_gf_xor(f, f.encode('utf-16-le')))] = _b64e(
            _gf_xor(f, fields[f].encode('utf-16-le')))
    plain = json.dumps(js, separators=(',', ':'), ensure_ascii=False)
    cap = GMC_SCRIPT_LEN // 2
    if len(plain) > cap:
        die('gmconfig_synth: 值太长（JSON %d > %d）' % (len(plain), cap))
    plain += ' ' * (cap - len(plain))
    body = gmconfig_xor(gmconfig_create_key(), plain.encode('utf-16-le'))
    head = bytearray(GMC_SCRIPT_OFF)
    struct.pack_into('<I', head, GMC_NAME_OFF, GMC_NAMELEN)
    head[GMC_NAME_OFF + 4:GMC_NAME_OFF + 4 + GMC_NAMELEN] = GMC_NAME.encode('ascii')
    struct.pack_into('<I', head, GMC_LEN_OFF, GMC_SCRIPT_LEN)
    return bytes(head) + body + b'\x00\x00'


def self_test():
    import zipfile
    tmp = tempfile.mkdtemp(prefix='batest')
    log('[*] self-test 目录 %s' % tmp)
    ok = True

    def check(cond, msg):
        nonlocal ok
        log('    %s %s' % ('[ok]  ' if cond else '[FAIL]', msg))
        ok = ok and bool(cond)
        return cond

    def expect_die(msg, fn):
        nonlocal ok
        try:
            fn()
        except SystemExit:
            log('    [ok]   拒绝：%s' % msg)
            return True
        log('    [FAIL] 没有拒绝：%s' % msg)
        ok = False
        return False

    # ---- A. GameMainConfig 算法锚点 ----
    log('[*] A. 算法锚点（对照 CRYPTO_MT.py 自检真值）')
    check(xxhash32(b'') == 0x02CC5D05, "xxHash32('') = 0x02CC5D05")
    check(xxhash32(b'abc') == 0x32D153FF, "xxHash32('abc') = 0x32D153FF")
    check(gmconfig_create_key().hex() == '1b232806ad72c257',
          "create_key('GameMainConfig') = 1b 23 28 06 ad 72 c2 57")

    # ---- B. 合成 asset 的等长替换 ----
    log('[*] B. GameMainConfig 等长替换（合成 5,212 B asset）')
    base = gmconfig_synth()
    check(len(base) == GMC_SIZE, '合成 asset = %d B' % len(base))
    i0 = gmconfig_read(base)
    check(i0['script_len'] == GMC_SCRIPT_LEN, 'm_Script = %d B' % i0['script_len'])
    check(len(i0['fields']) == 6, '6 个字段全解出')
    cap, _b, maxu, cur, doc = gmconfig_budget(i0)
    check(cap == 545 and doc == 101 and cur == 101,
          '预算 cap=%d 字符 / 保守上限=%d / 原值=%d；精确上限=%d'
          % (cap, doc, cur, maxu))

    dom = 'bapsvr-prods-cn.com'                      # 19 字符
    if not check(len(dom) == 19, '测试域名 %r = %d 字符' % (dom, len(dom))):
        return 1
    v_http = gmconfig_value_from_spec(dom)
    check(len(v_http) == 101, 'C 路径（http + 19 字符域名）value = %d 字符' % len(v_http))
    new_http, st = gmconfig_rewrite(base, v_http)
    check(len(new_http) == GMC_SIZE, '产物 %d B（等长）' % len(new_http))
    check(st['pad'] == 0, '无需补空格（JSON %d/545）' % st['json_len'])
    check(new_http[:GMC_SCRIPT_OFF] == base[:GMC_SCRIPT_OFF], '0x0..0x1018 头部逐字节不变')
    check(new_http[GMC_SCRIPT_OFF + 1090:] == base[GMC_SCRIPT_OFF + 1090:],
          '尾部 padding 不变')
    r = gmconfig_read(new_http)
    check(r['fields'][GMC_URL_FIELD] == v_http, '反解 ServerInfoDataUrl == 新值')
    check(all(r['fields'][f] == i0['fields'][f] for f in GMC_FIELDS
              if f != GMC_URL_FIELD), '其余 5 字段反解后逐字段未变')
    check(all(r['json'][r['keys'][f]] == i0['json'][i0['keys'][f]] for f in GMC_FIELDS
              if f != GMC_URL_FIELD), '其余 5 字段密文 b64 逐字节未变')
    log('    密文差异 %d B（原 %r）' % (st['diff'], i0['fields'][GMC_URL_FIELD]))

    # https + 18 字符域名（方案 A，也刚好 101 字符）
    v_a = gmconfig_value_from_spec('bapsvr-prod-cn.com', 'https')
    check(len(v_a) == 101, '方案 A（https + 18 字符域名）value = %d 字符' % len(v_a))
    new_a, st_a = gmconfig_rewrite(base, v_a)
    check(len(new_a) == GMC_SIZE and st_a['pad'] == 0,
          '方案 A 产物 %d B / 补 %d 空格 / 密文差异 %d B'
          % (len(new_a), st_a['pad'], st_a['diff']))

    # 短值 + 尾部空格补齐（方案 B）
    v_b = '["https://ba.example.com/si.json"]'
    new_b, st_b = gmconfig_rewrite(base, v_b)
    check(len(new_b) == GMC_SIZE and st_b['pad'] > 0,
          '方案 B 短值 %d 字符 -> 补 %d 空格 -> %d B' % (len(v_b), st_b['pad'], len(new_b)))
    check(gmconfig_read(new_b)['fields'][GMC_URL_FIELD] == v_b, '方案 B 反解一致')
    expect_die('短值 + --no-gmconfig-pad',
               lambda: gmconfig_rewrite(base, v_b, allow_pad=False))

    # ---- C. 拒绝：超长 ----
    log('[*] C. 非法输入必须拒绝（预算超限）')
    expect_die('http + 40 字符域名',
               lambda: gmconfig_rewrite(base, gmconfig_value_from_spec('a' * 40)))
    expect_die('https + 19 字符域名（value 103 字符）',
               lambda: gmconfig_rewrite(
                   base, gmconfig_value_from_spec('bapsvr-prods-cn.com', 'https')))
    expect_die('单条 URL 101 字符（value 105）',
               lambda: gmconfig_rewrite(base, gmconfig_value_from_spec(
                   'http://x/' + 'a' * 92)))
    expect_die('坏 asset（长度 5211）',
               lambda: gmconfig_read(base[:-1]))

    # ---- D. cert/私钥配对校验（AUDIT P1-4）----
    log('[*] D. cert/私钥配对校验')
    key = rsa_generate(1024)
    cert = build_self_signed_cert(key, cn='ba')
    check(assert_key_pair(key, cert), '配对的 key/cert 通过')
    k2 = rsa_generate(1024)
    c2 = build_self_signed_cert(k2, cn='other')
    expect_die('key A + cert B',
               lambda: assert_key_pair(key, c2, '--key-pem/--cert-pem: '))

    # ---- E. 打包 + 全部校验 ----
    log('[*] E. 打包 -> 校验（v1/v2/v3 + GameMainConfig 自检）')
    src = os.path.join(tmp, 'tiny.apk')
    longname = ('assets/audio/voc_jp/char_10041/'
                'shirokoridingsuit_battle_tacticalaction_1.ogg')
    with zipfile.ZipFile(src, 'w', zipfile.ZIP_STORED) as z:
        z.writestr('AndroidManifest.xml', b'\x03\x00\x08\x00\x0c\x00\x00\x00')
        z.writestr(NSC_ENTRY, b'\x03\x00\x08\x00\x08\x01\x00\x00')   # 假占位
        z.writestr('resources.arsc', struct.pack('<HHI', 0x0002, 12, 12))
        z.writestr(SDKCFG_ENTRY,
                   b'{\n "sdk_url": "https://sdk-api.yostar.cn",\n "x": 1\n}\n')
        z.writestr(SPARE_RAW_ENTRY, b'\x00' * 64)
        z.writestr(longname, b'\x00' * 32)          # 逼出 > 72 B 的 Name: 行
        z.writestr(GMC_ENTRY, base)
        for n in TPINFO_ENTRIES:
            z.writestr(n, b'\x00' * 8)
    log('[*] 测试证书 SHA-256 = %s' % hashlib.sha256(cert).hexdigest().upper())
    out = os.path.join(tmp, 'out.apk')
    do_build(src, out, 'https://example.test', None, 'user', key, cert, v1_on=True,
             gmconfig_value=v_http)
    ok = verify(out) and ok

    # ---- F. 签名器四项修复的显式证据 ----
    log('[*] F. 签名器修复项取证')
    with zipfile.ZipFile(out) as z:
        mf = z.read('META-INF/MANIFEST.MF')
        sf = z.read('META-INF/CERT.SF')
        names = z.namelist()
    lens = [len(x) for x in mf.split(b'\r\n')]
    check(max(lens) <= 72, 'MANIFEST.MF 最长行 %d B ≤ 72（原实现最长 92 B）' % max(lens))
    check(any(x.startswith(b' ') for x in mf.split(b'\r\n')),
          '有续行（首字节空格），signapk 风格')
    check(b'X-Android-APK-Signed: 2, 3' in sf, '.SF 含 X-Android-APK-Signed: 2, 3')
    check(len([n for n in names if n.startswith('META-INF/')]) == 3,
          'META-INF 只有 MANIFEST.MF/CERT.SF/CERT.RSA')
    gi = gmconfig_selfcheck(out, expect_value=v_http)
    check(gi['fields'][GMC_URL_FIELD] == v_http, '产物 APK 回读 ServerInfoDataUrl 正确')

    log('[*] self-test %s' % ('PASS' if ok else 'FAIL'))
    if ok:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        log('[!] 保留 %s 供排查' % tmp)
    return 0 if ok else 1


def gmconfig_selftest(src_path, domain=None, scheme=None, out_dir=None):
    """用真实源包里的 GameMainConfig 跑替换/拒绝/回读（不构建 APK）。"""
    dom = gmconfig_domain_token(domain) or 'bapsvr-prods-cn.com'
    out_dir = out_dir or os.path.dirname(os.path.abspath(__file__))
    ok = True

    def check(cond, msg):
        nonlocal ok
        log('    %s %s' % ('[ok]  ' if cond else '[FAIL]', msg))
        ok = ok and bool(cond)
        return cond

    def expect_die(msg, fn):
        nonlocal ok
        try:
            fn()
        except SystemExit:
            log('    [ok]   拒绝：%s' % msg)
            return True
        log('    [FAIL] 没有拒绝：%s' % msg)
        ok = False
        return False

    log('[*] 读源包 %s' % src_path)
    src = SrcZip(src_path)
    if not src.has(GMC_ENTRY):
        src.close()
        die('源包里没有 %s' % GMC_ENTRY)
    asset = src.read(GMC_ENTRY)
    src.close()
    log('    %s  %d B' % (GMC_ENTRY, len(asset)))
    info = gmconfig_read(asset)
    if not check(len(info['fields']) == 6, '6 个字段全解出'):
        return 1
    for f in GMC_FIELDS:
        log('      %-18s = %r' % (f, info['fields'][f]))
    cap, b, maxu, cur, doc = gmconfig_budget(info)
    log('    预算：cap=%d 字符（m_Script 1090 B），固定开销=%d，原值=%d，'
        '上限=%d(保守)/%d(精确)'
        % (cap, b, cur, doc, maxu))

    v_http = gmconfig_value_from_spec(dom, scheme or 'http')
    log('[*] C 路径：http + %d 字符域名 -> value %d 字符' % (len(dom), len(v_http)))
    new, st = gmconfig_rewrite(asset, v_http)
    out = os.path.join(out_dir, 'GameMainConfig_http_%s.bin' % dom)
    open(out, 'wb').write(new)
    check(len(new) == GMC_SIZE, '产物 %d B（等长）' % len(new))
    check(st['pad'] == 0, 'layer1 JSON %d/545，无需补空格' % st['json_len'])
    check(st['diff'] > 0, '密文差异 %d B（范围 0x%X..0x%X）'
          % (st['diff'], st['diff_range'][0], st['diff_range'][1]))
    log('    [write] %s' % out)
    chk = gmconfig_read(open(out, 'rb').read())
    check(chk['fields'][GMC_URL_FIELD] == v_http, '落盘后反解 == 新值')
    check(all(chk['fields'][f] == info['fields'][f] for f in GMC_FIELDS
              if f != GMC_URL_FIELD), '其余 5 字段逐字段未变')
    check(all(chk['json'][chk['keys'][f]] == info['json'][info['keys'][f]]
              for f in GMC_FIELDS if f != GMC_URL_FIELD), '其余 5 字段密文 b64 未变')
    check(open(out, 'rb').read()[:GMC_SCRIPT_OFF] == bytes(asset[:GMC_SCRIPT_OFF]),
          '头部/长度字段逐字节不变')

    log('[*] 方案 A：https + 18 字符域名')
    v_a = gmconfig_value_from_spec('bapsvr-prod-cn.com', 'https')
    new_a, st_a = gmconfig_rewrite(asset, v_a)
    check(len(v_a) == 101 and st_a['pad'] == 0,
          'value %d 字符，密文差异 %d B' % (len(v_a), st_a['diff']))

    log('[*] 拒绝测试')
    expect_die('http + 40 字符域名',
               lambda: gmconfig_rewrite(asset, gmconfig_value_from_spec('a' * 40)))
    expect_die('https + 19 字符域名（value 103）',
               lambda: gmconfig_rewrite(
                   asset, gmconfig_value_from_spec(dom, 'https')))
    log('[*] gmconfig-selftest %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# 14. CLI
# ---------------------------------------------------------------------------
def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    ap = argparse.ArgumentParser(
        description='BA 国服免 root 改造包构建器（纯 Python）',
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('--src')
    ap.add_argument('--out')
    ap.add_argument('--sdk-url')
    ap.add_argument('--ca')
    ap.add_argument('--ca-mode', default='user',
                    choices=['user', 'system', 'both', 'bundled'])
    ap.add_argument('--keystore', default='ba_private.keystore')
    ap.add_argument('--storepass', default='baserver')
    ap.add_argument('--keypass', default=None)
    ap.add_argument('--alias', default='ba')
    ap.add_argument('--key-pem')
    ap.add_argument('--cert-pem')
    ap.add_argument('--v1', dest='v1', action='store_true', default=True)
    ap.add_argument('--no-v1', dest='v1', action='store_false')
    ap.add_argument('--no-arsc-first', dest='arsc_first', action='store_false', default=True)
    ap.add_argument('--align-mode', default='raw', choices=['raw', 'd935', 'none'])
    ap.add_argument('--gmconfig-url', metavar='URL_OR_DOMAIN',
                    help='改 GameMainConfig.ServerInfoDataUrl（等长）。'
                         '可给域名 bapsvr-prods-cn.com（默认 http，19 字符最优）'
                         '或 http(s)://state-api.<域名>/api/state 或任意 URL')
    ap.add_argument('--gmconfig-value', metavar='STR',
                    help='直接给完整的 ServerInfoDataUrl 值（含 [] 的整串）')
    ap.add_argument('--gmconfig-scheme', choices=['http', 'https'],
                    help='强制协议（默认取自输入；纯域名默认 http）')
    ap.add_argument('--no-gmconfig-pad', dest='gmconfig_pad', action='store_false',
                    default=True, help='新值比原值短时不允许补尾部空格')
    ap.add_argument('--asset-replace', action='append', default=[],
                    metavar='NAME=PATH',
                    help='通用替换：zip 内条目名=本地文件（可多次）；'
                         '若换 GameMainConfig 会强制结构与字段自检')
    ap.add_argument('--gmconfig-selftest', action='store_true',
                    help='只测 GameMainConfig 替换算法（需 --src），不构建 APK')
    ap.add_argument('--gen-keystore', metavar='PATH')
    ap.add_argument('--verify-only', metavar='APK')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args(argv)

    if a.self_test:
        return self_test()
    if a.gen_keystore:
        gen_keystore(a.gen_keystore, a.storepass, a.alias)
        return 0
    if a.gmconfig_selftest:
        if not a.src:
            ap.error('--gmconfig-selftest 需要 --src')
        return gmconfig_selftest(a.src, a.gmconfig_url, a.gmconfig_scheme)
    if a.verify_only:
        exp = None
        if a.gmconfig_url or a.gmconfig_value:
            exp = gmconfig_value_from_spec(a.gmconfig_value or a.gmconfig_url,
                                           a.gmconfig_scheme)
        return 0 if verify(a.verify_only, require_v1=a.v1,
                           expect_gmconfig=exp) else 1
    if not a.src or not a.out:
        ap.error('需要 --src 与 --out')

    gmval = None
    if a.gmconfig_value and a.gmconfig_url:
        ap.error('--gmconfig-url 与 --gmconfig-value 只能给一个')
    if a.gmconfig_value or a.gmconfig_url:
        gmval = gmconfig_value_from_spec(a.gmconfig_value or a.gmconfig_url,
                                         a.gmconfig_scheme)
    rep = {}
    for spec in a.asset_replace:
        if '=' not in spec:
            ap.error('--asset-replace 格式是 NAME=PATH：%r' % spec)
        nm, _, pth = spec.partition('=')
        nm, pth = nm.strip(), pth.strip()
        if not nm or not pth:
            ap.error('--asset-replace 格式是 NAME=PATH：%r' % spec)
        if nm in rep:
            ap.error('--asset-replace 重复给了 %s' % nm)
        rep[nm] = pth

    key, cert = load_key(a.keystore, a.storepass, a.key_pem, a.cert_pem)
    log('=' * 74)
    log(' BA 国服免 root 改造')
    log(' src : %s (%s)' % (a.src, human(os.path.getsize(a.src))))
    log(' out : %s' % a.out)
    if gmval:
        log(' state: %r' % gmval)
    log('=' * 74)
    do_build(a.src, a.out, a.sdk_url, a.ca, a.ca_mode, key, cert,
             v1_on=a.v1, arsc_first=a.arsc_first, align_mode=a.align_mode,
             gmconfig_value=gmval, gmconfig_pad=a.gmconfig_pad,
             asset_replace=rep)
    ok = verify(a.out, require_v1=a.v1, expect_gmconfig=gmval)
    log('')
    log(' 输出 %s (%s)' % (a.out, human(os.path.getsize(a.out))))
    if not ok:
        log('!! 校验未通过，别装机 !!')
        return 1
    log(' 结果：OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
