#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRYPTO_MT.py -- BA (Blue Archive) Unity TextAsset / ZIP password crypto.

公式来源（两份独立证据，互相印证）:
  report/56-外部情报-国服私服与客户端绕过.md :1013-1097   (§10.5 口令算法 + 参考实现)
  report/56 :967-997                                      (§10.4 GameMainConfig / ServerInfoDataUrl)

算法链:
    seed      = xxHash32(UTF8(name), seed=0)
    mt        = MT19937(seed)
    mt.Next() = (genrand_int32() >> 1) & 0x7FFFFFFF      # 注意>>1，不是直接 genrand_int32
    NextBytes(n): 每 4 字节调一次 Next()，struct.pack('<I') 小端写入
    create_key(name)          -> NextBytes(8)             # 8 字节 XOR key (GameMainConfig)
    create_password(name, 20) -> b64encode(NextBytes(15)) # 20 字符 zip 口令
    xor_bytes(name, data)     -> 连续 keystream, 每 4 字节换一次 Next()

自检真值 (硬判据, report/56:1022 + :1096):
    create_password("Excel.zip") == "/wy5f3hIGGXLOIUDS9DZ"

用法:
    python CRYPTO_MT.py            # 跑自检
    from CRYPTO_MT import create_key, create_password, xor_bytes, MT, xxhash32
"""
import base64
import struct
import sys

M = 0xFFFFFFFF

# ---------------- xxHash32 (seed=0) ----------------
P1, P2, P3, P4, P5 = 2654435761, 2246822519, 3266489917, 668265263, 374761393


def _rotl(x, r):
    x &= M
    return ((x << r) | (x >> (32 - r))) & M


def xxhash32(data: bytes, seed: int = 0) -> int:
    """Canonical xxHash32. Used as MT19937 seed."""
    n = len(data)
    i = 0
    if n >= 16:
        v1 = (seed + P1 + P2) & M
        v2 = (seed + P2) & M
        v3 = seed & M
        v4 = (seed - P1) & M

        def _round(v, k):
            return (_rotl((v + (k * P2)) & M, 13) * P1) & M

        while i <= n - 16:
            v1 = _round(v1, struct.unpack_from('<I', data, i)[0]); i += 4
            v2 = _round(v2, struct.unpack_from('<I', data, i)[0]); i += 4
            v3 = _round(v3, struct.unpack_from('<I', data, i)[0]); i += 4
            v4 = _round(v4, struct.unpack_from('<I', data, i)[0]); i += 4
        h = (_rotl(v1, 1) + _rotl(v2, 7) + _rotl(v3, 12) + _rotl(v4, 18)) & M
    else:
        h = (seed + P5) & M

    h = (h + n) & M
    while i + 4 <= n:
        k = struct.unpack_from('<I', data, i)[0]; i += 4
        h = (_rotl((h + k * P3) & M, 17) * P4) & M
    while i < n:
        h = (_rotl((h + data[i] * P5) & M, 11) * P1) & M
        i += 1

    h ^= h >> 15; h = (h * P2) & M
    h ^= h >> 13; h = (h * P3) & M
    h ^= h >> 16
    return h & M


# ---------------- MT19937 (BA flavour) ----------------
class MT:
    """Standard MT19937 init_genrand(seed), BUT Next() is (genrand_int32()>>1)&0x7FFFFFFF.

    The >>1 is what makes BA's keystream bytes always < 0x80 on the high byte of
    each 4-byte group -- that is the tell in report/56:986.
    """

    def __init__(self, seed: int):
        self.mt = [0] * 624
        s = seed & M
        self.mt[0] = s
        for i in range(1, 624):
            self.mt[i] = (1812433253 * (self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) + i) & M
        self.idx = 624

    def genrand_int32(self) -> int:
        if self.idx >= 624:
            for i in range(624):
                y = (self.mt[i] & 0x80000000) | (self.mt[(i + 1) % 624] & 0x7FFFFFFF)
                v = self.mt[(i + 397) % 624] ^ (y >> 1)
                if y & 1:
                    v ^= 2567483615
                self.mt[i] = v & M
            self.idx = 0
        y = self.mt[self.idx]
        self.idx += 1
        y ^= y >> 11
        y ^= (y << 7) & 2636928640
        y ^= (y << 15) & 4022730752
        y ^= y >> 18
        return y & M

    def Next(self) -> int:
        return (self.genrand_int32() >> 1) & 0x7FFFFFFF

    def NextBytes(self, length: int) -> bytes:
        out = bytearray(length)
        i = 0
        while i < length:
            b = struct.pack('<I', self.Next())
            for j in range(4):
                if i + j < length:
                    out[i + j] = b[j]
            i += 4
        return bytes(out)


def _seed(name):
    return xxhash32(name.encode('utf-8'))


# ---------------- BA entry points ----------------
def create_key(name: str) -> bytes:
    """8-byte XOR key derived from an asset name. Used for TextAsset decryption."""
    return MT(_seed(name)).NextBytes(8)


def create_password(name: str, length: int = 20) -> str:
    """SharpZipLib zip password (20 chars) for TableBundles/*.zip / MediaResources."""
    return base64.b64encode(MT(_seed(name)).NextBytes((length * 3) // 4)).decode()


def keystream(name: str, n: int) -> bytes:
    """Continuous MT keystream, n bytes (Next() per 4 bytes, little-endian)."""
    return MT(_seed(name)).NextBytes(n)


def xor_bytes(name: str, data: bytes) -> bytes:
    """Table-inner second-layer XOR. Self-inverse. Continuous keystream (/= 8-byte repeat)."""
    mt = MT(_seed(name))
    out = bytearray(data)
    k = 0
    for i in range(len(out)):
        if i & 3 == 0:
            k = mt.Next()
        out[i] ^= (k >> ((i & 3) * 8)) & 0xFF
    return bytes(out)


def xor_with_key8(key8: bytes, data: bytes, offset: int = 0) -> bytes:
    """XOR with a fixed 8-byte key cycled -- the 'period 8' reading of report/56:985.

    This is create_key()'s first 8 keystream bytes reused, NOT the continued MT
    stream. Both hypotheses are tried by find_gamemainconfig.py; whichever yields
    JSON wins. offset = phase inside the 8-byte cycle (0 when starting at the
    TextAsset's m_Script start).
    """
    n = len(data)
    reps = (n // 8) + 1
    ks = (key8 * reps)[offset:offset + n]
    return bytes(a ^ b for a, b in zip(data, ks))


# ---------------- self-test ----------------
SELFTEST_PASSWORD = "/wy5f3hIGGXLOIUDS9DZ"      # report/56:1022 & :1096  (20 chars)


def selftest(verbose: bool = True) -> bool:
    ok = True
    pw = create_password("Excel.zip")
    g = pw == SELFTEST_PASSWORD
    ok &= g
    if verbose:
        print("[selftest] xxHash32('') =", hex(xxhash32(b'')), "(canonical 0x02CC5D05)")
        print("[selftest] xxHash32('abc') =", hex(xxhash32(b'abc')), "(canonical 0x32D153FF)")
        print("[selftest] seed xxhash32('Excel.zip') =", hex(_seed("Excel.zip")))
        print("[selftest] create_password('Excel.zip') =", repr(pw), "len", len(pw))
        print("[selftest] expected                     =", repr(SELFTEST_PASSWORD), "len", len(SELFTEST_PASSWORD))
        print("[selftest] create_key('GameMainConfig') =", create_key("GameMainConfig").hex(' '), "len 8")
        print("[selftest] RESULT:", "PASS" if g else "FAIL")
    return ok


if __name__ == '__main__':
    sys.exit(0 if selftest() else 1)
