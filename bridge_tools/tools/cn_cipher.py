# -*- coding: utf-8 -*-
"""cn_cipher.py — 国服《碧蓝档案》网关信封 编解码（已破解，实测可用）

实测结构
========
packet (base64) 解码后：
    [u32 LE 明文长度][gzip( 432 字节内层 )]
内层 432 字节：
    [ iv : 16 ][ AES-256-CBC 密文 : 384 ][ key : 32 (ASCII) ]
    key = 最后 32 字节的 **ASCII 原文本身**（例如 b"MjRlMmQ1MmNiZDg0Mzc2MjBjZTgwOTI3"）
明文 = PKCS7 去填充后的 373 字节 **JSON 片段**（以 ',' 开头）

完整的业务 JSON = '{"Protocol":"<名字>"' + 片段
    —— 即 `{"Protocol":"<名字>"` 这一段在密文之外，由 `protocol` 表单字段标识。

`protocol` 表单字段 = base32(16 字节)，跨请求固定，与 key 无关，可作为协议名的查找键。
"""

import base64
import gzip
import io
import json
import struct
import sys
import os

# [PATCH-PY-20261118v2] 解压上限（防 gzip 炸弹）
MAX_INFLATED_BYTES = 67108864

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aes_pure  # noqa: E402

INNER_LEN = 432
IV_OFF, IV_LEN = 0, 16
CT_OFF, CT_LEN = 16, 384
KEY_OFF, KEY_LEN = 400, 32

# protocol 字段 -> 协议名（按实测 / 观察累积）
PROTOCOL_MAP = {
    "AHTQLQI65FWJGGGK4KL5AEF57A": "Account_Auth",
}


def b32(s: str) -> bytes:
    return base64.b32decode(s + "=" * ((8 - len(s) % 8) % 8))


def protocol_name(protocol_field: str):
    return PROTOCOL_MAP.get(protocol_field)


def unwrap_packet(packet_b64: str) -> bytes:
    """packet(base64) -> gunzip 出来的 432 字节内层"""
    raw = base64.b64decode(packet_b64 + "=" * ((4 - len(packet_b64) % 4) % 4))
    if len(raw) < 6:
        raise ValueError("packet too short")
    declared = struct.unpack("<I", raw[:4])[0]
    if declared > MAX_INFLATED_BYTES:
        raise ValueError("declared length %d exceeds cap %d" % (declared, MAX_INFLATED_BYTES))
    with gzip.GzipFile(fileobj=io.BytesIO(raw[4:])) as gz:
        inner = gz.read(MAX_INFLATED_BYTES + 1)
    if len(inner) > MAX_INFLATED_BYTES:
        raise ValueError("inflated payload exceeds cap %d" % MAX_INFLATED_BYTES)
    if len(inner) != INNER_LEN:
        # 不强制，但报告
        print("[warn] inner len %d != %d" % (len(inner), INNER_LEN), file=sys.stderr)
    if declared != len(inner):
        print("[warn] declared %d != actual %d" % (declared, len(inner)), file=sys.stderr)
    return inner


def split_inner(inner: bytes):
    """内层 = [iv:16][ct:...][key:32]，长度可变（本样本恰为 432）"""
    if len(inner) < IV_LEN + KEY_LEN + 16:
        raise ValueError("inner too short: %d" % len(inner))
    return inner[:IV_LEN], inner[IV_LEN:len(inner) - KEY_LEN], inner[len(inner) - KEY_LEN:]


def pkcs7_unpad(data: bytes, bs: int = 16) -> bytes:
    n = data[-1] if data else 0
    if 1 <= n <= bs and data.endswith(bytes([n]) * n):
        return data[:-n]
    return data


def pkcs7_pad(data: bytes, bs: int = 16) -> bytes:
    n = bs - (len(data) % bs)
    return data + bytes([n]) * n


def decrypt_inner(inner: bytes):
    """-> (fragment_bytes, iv, key)"""
    iv, ct, key = split_inner(inner)
    if len(key) not in (16, 24, 32):
        raise ValueError("bad key length %d" % len(key))
    pt = aes_pure.cbc_decrypt(key, iv, ct)
    return pkcs7_unpad(pt), iv, key


def decode_packet(packet_b64: str, protocol_field: str = None):
    """一站式：-> dict {fragment, json(dict|None), iv, key, protocol_name}"""
    inner = unwrap_packet(packet_b64)
    frag, iv, key = decrypt_inner(inner)
    name = protocol_name(protocol_field) if protocol_field else None
    full = None
    text = frag.decode("utf-8", "replace")
    if name:
        try:
            full = json.loads('{"Protocol":"%s"' % name + text)
        except Exception:
            full = None
    return {"fragment": text, "json": full, "iv": iv.hex(), "key": key.decode("ascii", "replace"),
            "inner_len": len(inner), "frag_len": len(frag)}


# ------------------------------------------------------------------ 反向：打包
def build_inner(fragment_text: str, key: bytes = None, iv: bytes = None) -> bytes:
    """把 JSON 片段（以 ',' 开头）重新打包成 432 字节内层。

    不指定 key/iv 时随机生成（与客户端行为一致：每包一个新 key）。
    """
    import os as _os
    if key is None:
        key = base64.b64encode(_os.urandom(24))          # 32 字节 ASCII，与客户端同款
    if iv is None:
        iv = _os.urandom(16)
    ct = aes_pure.cbc_encrypt(key, iv, pkcs7_pad(fragment_text.encode("utf-8")))
    if len(ct) != CT_LEN:
        print("[warn] ct len %d != %d（只有参数长度恰好时才等长）" % (len(ct), CT_LEN),
              file=sys.stderr)
    return iv + ct + key


def wrap_packet(inner: bytes) -> str:
    body = gzip.compress(inner)
    raw = struct.pack("<I", len(inner)) + body
    return base64.b64encode(raw).decode()


# ------------------------------------------------------------------ Shittim .mx
SHITTIM_XOR = 0xD9


def build_mx(json_obj) -> bytes:
    """打包成 Shittim `/api/gateway` 能吃的 .mx"""
    payload = json.dumps(json_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    gz = gzip.compress(payload)
    body = struct.pack("<I", len(payload)) + gz
    enc = bytes(b ^ SHITTIM_XOR for b in body)
    return struct.pack("<I", 0) + struct.pack("<i", 0) + bytes([0, 0]) + enc


# ------------------------------------------------------------------ CLI
def _main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--selftest":
        frag = ',"DevId":"1","Token":"t","Hash":1}'
        inner = build_inner(frag)
        back, iv, key = decrypt_inner(inner)
        print("selftest roundtrip:", "OK" if back.decode() == frag else "FAIL")
        print("inner len:", len(inner), "key:", key.decode())
        return
    if len(sys.argv) < 2:
        print("usage: cn_cipher.py <packet_b64_file_or_string> [protocol_field]")
        print("       cn_cipher.py --selftest")
        return
    arg = sys.argv[1]
    b64 = open(arg, encoding="utf-8").read().strip() if os.path.exists(arg) else arg
    pf = sys.argv[2] if len(sys.argv) > 2 else None
    r = decode_packet(b64, pf)
    print(json.dumps({k: v for k, v in r.items() if k != "json"}, ensure_ascii=False, indent=2))
    if r["json"]:
        print("--- full JSON ---")
        print(json.dumps(r["json"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()
