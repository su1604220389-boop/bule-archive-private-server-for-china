# -*- coding: utf-8 -*-
"""aes_pure.py — 纯 Python AES（FIPS-197），无第三方依赖。
仅实现**解密**（ECB / CBC），供 mx_decode.py 在没有 cryptography 时兜底。
"""

SBOX = [
0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
]
INV_SBOX = [0] * 256
for _i, _v in enumerate(SBOX):
    INV_SBOX[_v] = _i

RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36,0x6c,0xd8,0xab,0x4d]


def _xtime(a):
    a <<= 1
    if a & 0x100:
        a = (a ^ 0x11b) & 0xff
    return a


def _mul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        a = _xtime(a)
        b >>= 1
    return r & 0xff


MUL2 = [_xtime(x) for x in range(256)]
MUL3 = [_mul(x, 3) for x in range(256)]
MUL9 = [_mul(x, 9) for x in range(256)]
MUL11 = [_mul(x, 11) for x in range(256)]
MUL13 = [_mul(x, 13) for x in range(256)]
MUL14 = [_mul(x, 14) for x in range(256)]


def _expand_key(key: bytes):
    nk = len(key) // 4
    if len(key) not in (16, 24, 32):
        raise ValueError("bad AES key length %d" % len(key))
    nr = {4: 10, 6: 12, 8: 14}[nk]
    w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
    for i in range(nk, 4 * (nr + 1)):
        t = list(w[i - 1])
        if i % nk == 0:
            t = t[1:] + t[:1]
            t = [SBOX[b] for b in t]
            t[0] ^= RCON[i // nk - 1]
        elif nk > 6 and i % nk == 4:
            t = [SBOX[b] for b in t]
        w.append([w[i - nk][j] ^ t[j] for j in range(4)])
    return [bytes(sum(w[4 * r:4 * r + 4], [])) for r in range(nr + 1)], nr


def _decrypt_block(block: bytes, rk, nr):
    s = [list(block[i:i + 4]) for i in range(0, 16, 4)]  # 4 rows x 4 cols? -> use column-major
    # 用列主序：state[r][c]
    state = [[block[r + 4 * c] for c in range(4)] for r in range(4)]

    def addrk(st, k):
        for r in range(4):
            for c in range(4):
                st[r][c] ^= k[r + 4 * c]

    addrk(state, rk[nr])
    for rnd in range(nr - 1, -1, -1):
        # InvShiftRows
        for r in range(1, 4):
            state[r] = state[r][-r:] + state[r][:-r]
        # InvSubBytes
        for r in range(4):
            for c in range(4):
                state[r][c] = INV_SBOX[state[r][c]]
        addrk(state, rk[rnd])
        if rnd:
            # InvMixColumns
            for c in range(4):
                a0, a1, a2, a3 = state[0][c], state[1][c], state[2][c], state[3][c]
                state[0][c] = MUL14[a0] ^ MUL11[a1] ^ MUL13[a2] ^ MUL9[a3]
                state[1][c] = MUL9[a0] ^ MUL14[a1] ^ MUL11[a2] ^ MUL13[a3]
                state[2][c] = MUL13[a0] ^ MUL9[a1] ^ MUL14[a2] ^ MUL11[a3]
                state[3][c] = MUL11[a0] ^ MUL13[a1] ^ MUL9[a2] ^ MUL14[a3]
    out = bytearray(16)
    for r in range(4):
        for c in range(4):
            out[r + 4 * c] = state[r][c]
    return bytes(out)


def ecb_decrypt(key: bytes, data: bytes) -> bytes:
    rk, nr = _expand_key(key)
    if len(data) % 16:
        raise ValueError("data not block aligned")
    return b"".join(_decrypt_block(data[i:i + 16], rk, nr) for i in range(0, len(data), 16))


def cbc_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    rk, nr = _expand_key(key)
    if len(data) % 16:
        raise ValueError("data not block aligned")
    prev = iv
    out = bytearray()
    for i in range(0, len(data), 16):
        blk = data[i:i + 16]
        dec = _decrypt_block(blk, rk, nr)
        out += bytes(a ^ b for a, b in zip(dec, prev))
        prev = blk
    return bytes(out)


def _encrypt_block(block: bytes, rk, nr):
    state = [[block[r + 4 * c] for c in range(4)] for r in range(4)]

    def addrk(st, k):
        for r in range(4):
            for c in range(4):
                st[r][c] ^= k[r + 4 * c]

    addrk(state, rk[0])
    for rnd in range(1, nr + 1):
        # SubBytes
        for r in range(4):
            for c in range(4):
                state[r][c] = SBOX[state[r][c]]
        # ShiftRows
        for r in range(1, 4):
            state[r] = state[r][r:] + state[r][:r]
        if rnd != nr:
            for c in range(4):
                a0, a1, a2, a3 = state[0][c], state[1][c], state[2][c], state[3][c]
                state[0][c] = MUL2[a0] ^ MUL3[a1] ^ a2 ^ a3
                state[1][c] = a0 ^ MUL2[a1] ^ MUL3[a2] ^ a3
                state[2][c] = a0 ^ a1 ^ MUL2[a2] ^ MUL3[a3]
                state[3][c] = MUL3[a0] ^ a1 ^ a2 ^ MUL2[a3]
        addrk(state, rk[rnd])
    out = bytearray(16)
    for r in range(4):
        for c in range(4):
            out[r + 4 * c] = state[r][c]
    return bytes(out)


def ecb_encrypt(key: bytes, data: bytes) -> bytes:
    rk, nr = _expand_key(key)
    if len(data) % 16:
        raise ValueError("data not block aligned")
    return b"".join(_encrypt_block(data[i:i + 16], rk, nr) for i in range(0, len(data), 16))


def cbc_encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    rk, nr = _expand_key(key)
    if len(data) % 16:
        raise ValueError("data not block aligned")
    prev = iv
    out = bytearray()
    for i in range(0, len(data), 16):
        blk = bytes(a ^ b for a, b in zip(data[i:i + 16], prev))
        enc = _encrypt_block(blk, rk, nr)
        out += enc
        prev = enc
    return bytes(out)


def pkcs7_pad(data: bytes, bs: int = 16) -> bytes:
    n = bs - (len(data) % bs)
    return data + bytes([n]) * n


if __name__ == "__main__":
    key = bytes(range(16))
    pt = bytes.fromhex("00112233445566778899aabbccddeeff")
    ct = ecb_encrypt(key, pt)
    print("AES-128 ECB encrypt:", ct.hex(),
          "OK" if ct.hex() == "69c4e0d86a7b0430d8cdb78070b4c55a" else "FAIL")
    # CBC 往返
    k2 = bytes(range(32)); iv = bytes(range(16, 32))
    msg = pkcs7_pad(b'{"Protocol":"Account_Auth","UID":314816420}')
    back = cbc_decrypt(k2, iv, cbc_encrypt(k2, iv, msg))
    print("AES-256 CBC roundtrip:", "OK" if back == msg else "FAIL")
    # FIPS-197 附录 C 测试向量（AES-128）
    ct0 = bytes.fromhex("69c4e0d86a7b0430d8cdb78070b4c55a")
    pt0 = ecb_decrypt(key, ct0)
    print("AES-128 ECB decrypt:", pt0.hex(),
          "OK" if pt0.hex() == "00112233445566778899aabbccddeeff" else "FAIL")
    key256 = bytes(range(32))
    ct256 = bytes.fromhex("8ea2b7ca516745bfeafc49904b496089")
    pt256 = ecb_decrypt(key256, ct256)
    print("AES-256 ECB decrypt:", pt256.hex(),
          "OK" if pt256.hex() == "00112233445566778899aabbccddeeff" else "FAIL")
