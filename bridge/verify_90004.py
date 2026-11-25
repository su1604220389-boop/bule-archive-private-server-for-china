#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_90004.py — 部署后一键验证 90004 Management_Data 的**键集合/类型/条数**是否与官方一致。

    # 在服务器上（bridge 监听 127.0.0.1:9097）
    python3 verify_90004.py
    # 指定地址 / 端口 / 预期文件
    python3 verify_90004.py --host 127.0.0.1 --port 9097
    python3 verify_90004.py --expected expected_90004.json --dump raw_90004.json

做什么
------
1. 按客户端同款容器（`cn_cipher`：`base64([u32 len][gzip(iv16|ct|key32)])`）加密一个
   90004 请求，`Hash = (90004<<32)|7`，POST 到 `/api/management/data`；
2. 按 `cn_wire` 容器（`base64(ct|key32)`，IV 固定 `JOSYdf8ys97uhFYS`）解出响应明文，
   再 `json.loads(packet)` 得到内层对象；
3. 与 `expected_90004.json` 比：顶层键集合 / Data 键集合 / 每个列表的条数 +
   逐元素逐字段的值 / 三个 null / 类型 / 旧 16 键残留 / SessionKey 合理性 /
   outer requestid == inner RequestId。

只依赖标准库（AES 是内联的纯 Python 实现，见文件末尾 `_AES`，摘自
`bapatch/tools/aes_pure.py`）——服务器上不需要 `cryptography`。

退出码
------
0 PASS    1 FAIL（有差异，明细已打印）    2 连不上 / 解码失败（结构无法判定）
"""
from __future__ import annotations

import argparse
import base64
import binascii
import datetime
import gzip
import hashlib
import json
import os
import re
import struct
import sys
import urllib.error
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXPECTED = os.path.join(HERE, "expected_90004.json")
DEFAULT_PATH = "/api/management/data"

PROTO = 90004
PROTO_NAME = "Management_Data"
HASH = (PROTO << 32) | 7          # 官方 06 抓包：386564236509191，低 32 位 = 7

# cn_wire：IV 固定，key 是密文尾部 32 字节
WIRE_IV = b"JOSYdf8ys97uhFYS"
WIRE_KEY_LEN = 32

# 顶层 6 键（官方 10/10 稳定的键序）
TOP_KEYS = ["Protocol", "SessionKey", "ServerTimeTicks", "ServerNotification",
            "RequestId", "Data"]
# Data 9 键（官方 10/10 稳定的键序）
DATA_KEYS = ["Notices", "Events", "Issues", "Banners", "GachaProbabilityDisplay",
             "GuidePopup", "GachaPeriodDisplay", "RaidPeriodDisplay", "Survey"]
NULL_KEYS = ("GachaPeriodDisplay", "RaidPeriodDisplay", "Survey")
LIST_KEYS = ("Notices", "Events", "Issues", "Banners", "GachaProbabilityDisplay", "GuidePopup")

# 旧实现多发的键（官方一次都没发过）——出现即 FAIL
LEGACY_EXTRA = ("ContentLock", "StaticOpenConditions", "MissionProgressDBs",
                "EventMissionProgressDBDict", "BattlePassMissionProgressDBDict")
# 官方 DTO 有、但序列化层从不发的 11 个字段（出现也算结构错）
DTO_SILENT = ("Maintenance", "ServerStatus", "LatestClientVersion",
              "LatestAndroidClientVersion", "LatestIosClientVersion", "LatestPCClientVersion",
              "MarketAppleId", "NotificationBeforeMaintenance", "DownloadLimitTime",
              "EnableSQLite")

VOLATILE_TOP = ("SessionKey", "ServerTimeTicks", "RequestId")


# ================================================================ AES（纯 Python）
class _AES(object):
    """FIPS-197 AES / CBC，纯 Python。摘自 bapatch/tools/aes_pure.py（项目内已验证）。"""

    SBOX = bytes((
        0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
        0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
        0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
        0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
        0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
        0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
        0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
        0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
        0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
        0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
        0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
        0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
        0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
        0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
        0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
        0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
    ))
    RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36, 0x6c, 0xd8, 0xab, 0x4d)

    @classmethod
    def _init_tables(cls):
        if hasattr(cls, "_READY"):
            return
        cls.INV = [0] * 256
        for i, v in enumerate(cls.SBOX):
            cls.INV[v] = i
        cls.M2 = [cls._xtime(x) for x in range(256)]
        cls.M3 = [cls._mul(x, 3) for x in range(256)]
        cls.M9 = [cls._mul(x, 9) for x in range(256)]
        cls.M11 = [cls._mul(x, 11) for x in range(256)]
        cls.M13 = [cls._mul(x, 13) for x in range(256)]
        cls.M14 = [cls._mul(x, 14) for x in range(256)]
        cls._READY = True

    @staticmethod
    def _xtime(a):
        a <<= 1
        return (a ^ 0x11b) & 0xff if a & 0x100 else a

    @staticmethod
    def _mul(a, b):
        r = 0
        while b:
            if b & 1:
                r ^= a
            a = _AES._xtime(a)
            b >>= 1
        return r & 0xff

    def __init__(self, key):
        self._init_tables()
        if len(key) not in (16, 24, 32):
            raise ValueError("bad AES key length %d" % len(key))
        nk = len(key) // 4
        self.nr = {4: 10, 6: 12, 8: 14}[nk]
        w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
        for i in range(nk, 4 * (self.nr + 1)):
            t = list(w[i - 1])
            if i % nk == 0:
                t = t[1:] + t[:1]
                t = [self.SBOX[b] for b in t]
                t[0] ^= self.RCON[i // nk - 1]
            elif nk > 6 and i % nk == 4:
                t = [self.SBOX[b] for b in t]
            w.append([w[i - nk][j] ^ t[j] for j in range(4)])
        self.rk = [bytes(sum(w[4 * r:4 * r + 4], [])) for r in range(self.nr + 1)]

    def _addrk(self, st, k):
        for r in range(4):
            for c in range(4):
                st[r][c] ^= k[r + 4 * c]

    def encrypt_block(self, blk):
        st = [[blk[r + 4 * c] for c in range(4)] for r in range(4)]
        self._addrk(st, self.rk[0])
        for rnd in range(1, self.nr + 1):
            for r in range(4):
                for c in range(4):
                    st[r][c] = self.SBOX[st[r][c]]
            for r in range(1, 4):
                st[r] = st[r][r:] + st[r][:r]
            if rnd != self.nr:
                for c in range(4):
                    a0, a1, a2, a3 = st[0][c], st[1][c], st[2][c], st[3][c]
                    st[0][c] = self.M2[a0] ^ self.M3[a1] ^ a2 ^ a3
                    st[1][c] = a0 ^ self.M2[a1] ^ self.M3[a2] ^ a3
                    st[2][c] = a0 ^ a1 ^ self.M2[a2] ^ self.M3[a3]
                    st[3][c] = self.M3[a0] ^ a1 ^ a2 ^ self.M2[a3]
            self._addrk(st, self.rk[rnd])
        out = bytearray(16)
        for r in range(4):
            for c in range(4):
                out[r + 4 * c] = st[r][c]
        return bytes(out)

    def decrypt_block(self, blk):
        st = [[blk[r + 4 * c] for c in range(4)] for r in range(4)]
        self._addrk(st, self.rk[self.nr])
        for rnd in range(self.nr - 1, -1, -1):
            for r in range(1, 4):
                st[r] = st[r][-r:] + st[r][:-r]
            for r in range(4):
                for c in range(4):
                    st[r][c] = self.INV[st[r][c]]
            self._addrk(st, self.rk[rnd])
            if rnd:
                for c in range(4):
                    a0, a1, a2, a3 = st[0][c], st[1][c], st[2][c], st[3][c]
                    st[0][c] = self.M14[a0] ^ self.M11[a1] ^ self.M13[a2] ^ self.M9[a3]
                    st[1][c] = self.M9[a0] ^ self.M14[a1] ^ self.M11[a2] ^ self.M13[a3]
                    st[2][c] = self.M13[a0] ^ self.M9[a1] ^ self.M14[a2] ^ self.M11[a3]
                    st[3][c] = self.M11[a0] ^ self.M13[a1] ^ self.M9[a2] ^ self.M14[a3]
        out = bytearray(16)
        for r in range(4):
            for c in range(4):
                out[r + 4 * c] = st[r][c]
        return bytes(out)

    def cbc_encrypt(self, iv, data):
        if len(data) % 16:
            raise ValueError("not block aligned")
        prev, out = iv, bytearray()
        for i in range(0, len(data), 16):
            blk = bytes(a ^ b for a, b in zip(data[i:i + 16], prev))
            enc = self.encrypt_block(blk)
            out += enc
            prev = enc
        return bytes(out)

    def cbc_decrypt(self, iv, data):
        if len(data) % 16:
            raise ValueError("not block aligned")
        prev, out = iv, bytearray()
        for i in range(0, len(data), 16):
            blk = data[i:i + 16]
            dec = self.decrypt_block(blk)
            out += bytes(a ^ b for a, b in zip(dec, prev))
            prev = blk
        return bytes(out)


def pkcs7_pad(data, bs=16):
    n = bs - (len(data) % bs)
    return data + bytes([n]) * n


def pkcs7_unpad(data, bs=16):
    if not data:
        raise ValueError("empty")
    n = data[-1]
    if not (1 <= n <= bs) or data[-n:] != bytes([n]) * n:
        raise ValueError("bad pkcs7 padding (last byte %d)" % n)
    return data[:-n]


def cbc_encrypt(key, iv, data):
    return _AES(key).cbc_encrypt(iv, data)


def cbc_decrypt(key, iv, data):
    return _AES(key).cbc_decrypt(iv, data)


# ================================================================ 请求（cn_cipher 容器）
def b32md5(name):
    """客户端请求里 protocol 字段的 token：base32(md5(name utf-16-le))。"""
    return base64.b32encode(hashlib.md5(name.encode("utf-16-le")).digest()).decode().rstrip("=")


def build_request_packet(fragment=None, key=None, iv=None):
    """→ (packet_b64, fragment, key, iv)

    容器 = base64( [u32 LE len(inner)] + gzip( [iv16][AES-256-CBC ct][key32] ) )
    fragment 以 ',' 开头：客户端只加密 `{"Protocol":<num>` 之后的部分。
    """
    fragment = fragment or ',"Hash":%d}' % HASH
    key = key or base64.b64encode(os.urandom(24))          # 32 字节 ASCII（与客户端同款）
    iv = iv or os.urandom(16)
    ct = cbc_encrypt(key, iv, pkcs7_pad(fragment.encode("utf-8")))
    inner = iv + ct + key
    raw = struct.pack("<I", len(inner)) + gzip.compress(inner)
    return base64.b64encode(raw).decode("ascii"), fragment, key, iv


def multipart_body(fields, boundary=None):
    """手搓 multipart/form-data：bridge 的 parse_cn_multipart 只认 name="..." 三件套。"""
    b = boundary or ("----ba90004" + uuid.uuid4().hex)
    out = []
    for k, v in fields.items():
        out.append(("--%s\r\n" % b).encode())
        out.append(('Content-Disposition: form-data; name="%s"\r\n\r\n' % k).encode())
        out.append(str(v).encode("utf-8"))
        out.append(b"\r\n")
    out.append(("--%s--\r\n" % b).encode())
    return b"".join(out), b


def decode_cn_wire(body):
    """响应：base64( AES-256-CBC(明文) 密文 + key32 )，IV 固定。→ (outer, inner, plain)"""
    if isinstance(body, str):
        body = body.encode()
    raw = base64.b64decode(body.strip())
    if len(raw) <= WIRE_KEY_LEN or (len(raw) - WIRE_KEY_LEN) % 16:
        raise ValueError("bad cn_wire length %d" % len(raw))
    ct, key = raw[:-WIRE_KEY_LEN], raw[-WIRE_KEY_LEN:]
    plain = pkcs7_unpad(cbc_decrypt(key, WIRE_IV, ct)).decode("utf-8")
    outer = json.loads(plain)
    pkt = outer.get("packet")
    inner = json.loads(pkt) if isinstance(pkt, str) else pkt
    return outer, inner, plain


def decode_any(body):
    """响应解码兜底链：cn_wire 容器 → 纯 JSON 信封 → cn_cipher gzip 容器。"""
    if isinstance(body, str):
        body = body.encode()
    errs = []
    try:
        o, i, p = decode_cn_wire(body)
        return o, i, "cn_wire", p, errs
    except Exception as e:
        errs.append("cn_wire: %r" % (e,))
    try:
        txt = body.decode("utf-8")
        o = json.loads(txt)
        if isinstance(o, dict) and "packet" in o:
            pkt = o["packet"]
            i = json.loads(pkt) if isinstance(pkt, str) else pkt
            return o, i, "json-envelope", txt, errs
    except Exception as e:
        errs.append("json-envelope: %r" % (e,))
    try:
        raw = base64.b64decode(body.strip())
        inner = gzip.decompress(raw[4:])
        iv, ct, key = inner[:16], inner[16:-32], inner[-32:]
        pt = pkcs7_unpad(cbc_decrypt(key, iv, ct)).decode("utf-8")
        o = json.loads(pt)
        pkt = o.get("packet") if isinstance(o, dict) else None
        i = json.loads(pkt) if isinstance(pkt, str) else o
        return o, i, "cn_cipher", pt, errs
    except Exception as e:
        errs.append("cn_cipher: %r" % (e,))
    raise ValueError("三种解码都失败: %s" % "; ".join(errs))


# ================================================================ HTTP
def probe(url, timeout=15.0, protocol_token=None, verbose=True):
    """打一次 90004，返回 dict(http/body/outer/inner/fmt/plain/req)。"""
    packet, frag, key, iv = build_request_packet()
    body, boundary = multipart_body({"protocol": protocol_token or b32md5(PROTO_NAME),
                                     "packet": packet})
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=%s" % boundary)
    req.add_header("Content-Length", str(len(body)))
    req.add_header("REQUEST-ID", str(uuid.uuid4()))
    req.add_header("User-Agent", "ba-90004-verify/1.0")
    req.add_header("Accept", "*/*")
    req.add_header("Connection", "close")
    out = {"url": url, "req_packet_len": len(packet), "req_fragment": frag,
           "req_hash": HASH}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out["status"] = r.status
            out["ct"] = r.headers.get("Content-Type", "")
            out["body"] = r.read()
    except urllib.error.HTTPError as e:
        out["status"] = e.code
        out["ct"] = e.headers.get("Content-Type", "") if e.headers else ""
        out["body"] = e.read() if e else b""
    if verbose:
        print("POST %s  (%d B, Hash=%d)" % (url, len(body), HASH))
        print("  -> HTTP %s / %d bytes / %s" % (out["status"], len(out["body"]),
                                                out.get("ct", "")))
    return out


# ================================================================ 比对
def tname(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "dict"
    return type(v).__name__


def diff_obj(exp, act, path, out, limit=200):
    """递归 diff，往 out 里塞人话；返回条数。"""
    n = 0
    if n >= limit:
        return n
    te, ta = tname(exp), tname(act)
    if te != ta:
        out.append("%s: 类型 %s，期望 %s" % (path, ta, te))
        return 1
    if isinstance(exp, dict):
        for k in exp:
            if k not in act:
                out.append("%s.%s: 缺键" % (path, k))
                n += 1
            else:
                n += diff_obj(exp[k], act[k], "%s.%s" % (path, k), out, limit - n)
        for k in act:
            if k not in exp:
                out.append("%s.%s: 多键（官方没有）" % (path, k))
                n += 1
        return n
    if isinstance(exp, list):
        if len(exp) != len(act):
            out.append("%s: 条数 %d，期望 %d" % (path, len(act), len(exp)))
            n += 1
        for i in range(min(len(exp), len(act))):
            n += diff_obj(exp[i], act[i], "%s[%d]" % (path, i), out, limit - n)
        return n
    if exp != act:
        out.append("%s: %r，期望 %r" % (path, act, exp))
        return 1
    return 0


def xor_diff(a, b, path, out, limit=200):
    """只比键集合（顶层/Data 这种「集合相等」的要求）。"""
    if not isinstance(a, dict) or not isinstance(b, dict):
        out.append("%s: 不是 dict" % path)
        return 1
    n = 0
    for k in b:
        if k not in a:
            out.append("%s: 缺键 %r" % (path, k))
            n += 1
    for k in a:
        if k not in b:
            extra = ""
            if k in LEGACY_EXTRA:
                extra = "  ← 旧 16 键平铺残留"
            elif k in DTO_SILENT:
                extra = "  ← DTO 里有、官方从不序列化"
            out.append("%s: 多键 %r%s" % (path, k, extra))
            n += 1
    return n


class Result(object):
    def __init__(self):
        self.rows = []
        self.fails = []

    def add(self, name, ok, detail="", warn=False):
        """warn=True = 软检查：不通过只记 WARN，不计入 FAIL。"""
        if warn:
            st = "PASS" if ok else "WARN"
        else:
            st = "PASS" if ok else "FAIL"
            if not ok:
                self.fails.append("%s: %s" % (name, detail))
        self.rows.append((st, name, detail))
        return ok

    def dump(self):
        w = max([len(r[1]) for r in self.rows] + [10])
        print("\n%-6s %-*s %s" % ("", w, "CHECK", "DETAIL"))
        print("-" * (w + 40))
        for st, name, detail in self.rows:
            print("%-6s %-*s %s" % ("[" + st + "]", w, name, detail))
        print("-" * (w + 40))
        nfail = sum(1 for r in self.rows if r[0] == "FAIL")
        nwarn = sum(1 for r in self.rows if r[0] == "WARN")
        print("%d checks / FAIL=%d / WARN=%d" % (len(self.rows), nfail, nwarn))
        return not self.fails


def now_ticks():
    """与 bridge 同口径：本地时钟的 .NET 100ns ticks（自 0001-01-01）。"""
    n = datetime.datetime.now()
    return int((n - datetime.datetime(1, 1, 1)).total_seconds()) * 10_000_000 + n.microsecond * 10


def verify(inner, outer, expected, res, raw_len=None):
    exp = expected

    # ---- 顶层
    got_top = list(inner) if isinstance(inner, dict) else []
    d = []
    n = xor_diff(inner, exp, "$", d) if isinstance(inner, dict) else 1
    res.add("顶层键集合（6 键）", n == 0,
            "got=%d %s%s" % (len(got_top), got_top if n == 0 else "",
                             "" if n == 0 else " | " + "; ".join(d[:6])))
    if n:
        diff_obj(exp, inner, "$", d, 40)
    order_ok = got_top == TOP_KEYS
    res.add("顶层键序（官方 10/10 稳定）", order_ok, " → ".join(got_top), warn=True)

    res.add("Protocol == 90004", inner.get("Protocol") == PROTO,
            "got=%r (%s)" % (inner.get("Protocol"), tname(inner.get("Protocol"))))

    # ---- 易变字段：只查类型/合理性
    sk = inner.get("SessionKey")
    sk_ok = isinstance(sk, dict) and set(sk) == {"AccountServerId", "MxToken"} \
        and isinstance(sk.get("AccountServerId"), int) and isinstance(sk.get("MxToken"), str)
    res.add("SessionKey 形状", sk_ok,
            "%r" % (sk,) if sk_ok else "got=%r" % (sk,))
    if sk_ok:
        empty = (not sk.get("AccountServerId")) or (not sk.get("MxToken"))
        res.add("SessionKey 非空", not empty,
                "AccountServerId=%r MxToken=%s" % (
                    sk.get("AccountServerId"),
                    "空（bridge 尚未登录过账号，不影响结构）" if not sk.get("MxToken")
                    else "len=%d" % len(sk.get("MxToken"))), warn=True)

    ticks = inner.get("ServerTimeTicks")
    t_ok = isinstance(ticks, int) and not isinstance(ticks, bool) and ticks > 0
    delta = (ticks - now_ticks()) if t_ok else None
    close = t_ok and abs(delta) < 600 * 10_000_000       # ±10 分钟
    res.add("ServerTimeTicks 合理", close,
            "got=%r (与本机 now 差 %.1f s)" % (ticks, (delta or 0) / 1e7))

    res.add("ServerNotification == 0", inner.get("ServerNotification") == 0,
            "got=%r" % (inner.get("ServerNotification"),))

    rid = inner.get("RequestId")
    rid_ok = isinstance(rid, str) and bool(re.match(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", rid))
    res.add("RequestId 是 uuid", rid_ok, "got=%r" % (rid,))

    if isinstance(outer, dict) and outer.get("requestid"):
        same = outer.get("requestid") == rid
        res.add("outer requestid == inner RequestId", same,
                "outer=%r inner=%r" % (outer.get("requestid"), rid))

    # ---- Data
    data = inner.get("Data")
    if not isinstance(data, dict):
        res.add("Data 是 dict（不是 null/缺省）", False, "got=%r (%s)" % (data, tname(data)))
        return res
    res.add("Data 是 dict（不是 null/缺省）", True, "%d 键" % len(data))

    d2 = []
    n2 = xor_diff(data, exp["Data"], "Data", d2)
    res.add("Data 键集合（9 键）", n2 == 0,
            "got=%d %s%s" % (len(data), list(data) if n2 == 0 else "",
                             "" if n2 == 0 else " | " + "; ".join(d2[:6])))
    res.add("Data 键序（官方 10/10 稳定）", list(data) == DATA_KEYS,
            " → ".join(list(data)), warn=True)
    if n2:
        diff_obj(exp["Data"], data, "Data", d2, 60)

    # ---- 逐键：类型 + 条数 + 值
    for k in DATA_KEYS:
        e = exp["Data"].get(k)
        a = data.get(k, "<missing>")
        if k in NULL_KEYS:
            ok = a is None
            res.add("Data.%s is null" % k, ok, "got=%r (%s)" % (a, tname(a)))
            continue
        if not isinstance(a, list):
            res.add("Data.%s 是 list" % k, False,
                    "got=%s %r  ← 旧实现这里是 False/{}" % (tname(a), a))
            continue
        elen = len(e) if isinstance(e, list) else -1
        res.add("Data.%s 条数" % k, len(a) == elen,
                "%d 条（期望 %d）" % (len(a), elen))
        # 元素类型 + 键集合
        bad = [i for i, x in enumerate(a) if not isinstance(x, dict)]
        res.add("Data.%s 元素是 dict" % k, not bad,
                "所有 %d 条都是 dict" % len(a) if not bad else "第 %s 条不是 dict" % bad[:5])

    # ---- 全量逐字节值比对（Data 是静态运营数据，应逐字节相同）
    exp_c = json.dumps(exp["Data"], ensure_ascii=False, separators=(",", ":"))
    got_c = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    same = exp_c == got_c
    res.add("Data 逐字节（紧凑 JSON）", same,
            "%d B (sha %s)" % (len(got_c.encode("utf-8")),
                               hashlib.sha256(got_c.encode("utf-8")).hexdigest()[:16])
            if same else "我们 %d B / 期望 %d B" % (
                len(got_c.encode("utf-8")), len(exp_c.encode("utf-8"))))
    if not same:
        dd = []
        diff_obj(exp["Data"], data, "Data", dd, 80)
        for ln in dd[:30]:
            print("    - %s" % ln)
        if len(dd) > 30:
            print("    ... 还有 %d 条差异" % (len(dd) - 30))

    # ---- 旧实现多发的键（顶层 + Data 内）
    bad_top = [k for k in LEGACY_EXTRA if k in inner]
    bad_data = [k for k in LEGACY_EXTRA if isinstance(data, dict) and k in data]
    res.add("无旧 16 键多余额外键", not bad_top and not bad_data,
            "无" if not bad_top and not bad_data else "顶层=%s Data=%s" % (bad_top, bad_data))

    # ---- 3 个键必须是 null 而不是 false/{}
    types_ok = (data.get("GachaProbabilityDisplay") is None or
                isinstance(data.get("GachaProbabilityDisplay"), list)) and \
               isinstance(data.get("GuidePopup"), list)
    res.add("GachaProbabilityDisplay/GuidePopup 是 list", types_ok,
            "GachaProbabilityDisplay=%s GuidePopup=%s" % (
                tname(data.get("GachaProbabilityDisplay")), tname(data.get("GuidePopup"))))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="验证 90004 Management_Data 的响应结构（与 expected_90004.json 比）")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9097)
    ap.add_argument("--path", default=DEFAULT_PATH)
    ap.add_argument("--url", default=None, help="完整 URL（覆盖 host/port/path）")
    ap.add_argument("--expected", default=DEFAULT_EXPECTED)
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--protocol-token", default=None,
                    help="multipart 里的 protocol 字段（默认 base32(md5())）")
    ap.add_argument("--dump", default=None, help="把解码后的内层对象写到这里")
    ap.add_argument("--raw", default=None, help="把原始响应体写到这里")
    a = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    url = a.url or "http://%s:%d%s" % (a.host, a.port, a.path)
    ep = os.path.abspath(a.expected)
    try:
        expected = json.load(open(ep, "r", encoding="utf-8"))
    except Exception as e:
        print("读不了 expected 文件 %s: %r" % (ep, e))
        return 2
    print("expected: %s (%d B)" % (ep, os.path.getsize(ep)))

    try:
        got = probe(url, a.timeout, a.protocol_token)
    except Exception as e:
        print("!! 请求失败（bridge 没起 / 端口不对 / 网络不通）: %r" % (e,))
        return 2
    body = got.get("body") or b""
    if a.raw:
        open(a.raw, "wb").write(body)
        print("raw body -> %s (%d B)" % (a.raw, len(body)))
    if got.get("status") != 200:
        print("!! HTTP %s，body 前 300 B: %r" % (got.get("status"), body[:300]))
        return 2

    try:
        outer, inner, fmt, plain, errs = decode_any(body)
    except Exception as e:
        print("!! 响应解码失败: %r" % (e,))
        print("   body 前 200 B: %r" % (body[:200],))
        return 2

    print("解码: %s  (plain %d B / inner %d 键)" % (fmt, len(plain), len(inner)))
    if a.dump:
        with open(a.dump, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(inner, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        print("decoded inner -> %s" % a.dump)

    res = Result()
    print()
    res.add("HTTP 200", True, "%d bytes" % len(body))
    verify(inner, outer, expected, res, raw_len=len(body))
    ok = res.dump()

    print()
    if ok:
        print("RESULT: PASS —— 90004 已是官方 6 层 + Data 9 键结构，与 expected_90004.json 一致")
        return 0
    print("RESULT: FAIL —— 见上面 [FAIL] 行")
    for f in res.fails:
        print("  x %s" % f)
    return 1


if __name__ == "__main__":
    sys.exit(main())
