#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FIX-3：relay/relay2 的响应信封改用 _cn_send_envelope（真名 + 真 Protocol）。

只改两个调用点，不动 _cn_envelope / _cn_enc_b64 / _cn_send_envelope 本体 / 任何开关。
"""
import hashlib, io, sys

SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
BASE_SHA = '9e02a5c8fce6ab1eeaff10be9270ad3fa92b0f33c444ca7ab47a674eea4ad489'

OLD1 = "                _rl_a = rl_route(rec, proto_str, packet_b64, name, self._cn_envelope)"
NEW1 = ("                _rl_a = rl_route(rec, proto_str, packet_b64, name,\n"
        "                                 lambda _nm, _obj, _rec: self._cn_send_envelope(\n"
        "                                     name_fix_resolve(proto_str, _rec) or _nm, _obj, _rec))   # FIX-3 v1")

OLD2 = "            _rl2_a = rl2_route(rec, proto_str, packet_b64, name, self._cn_envelope)"
NEW2 = ("            _rl2_a = rl2_route(rec, proto_str, packet_b64, name,\n"
        "                               self._cn_send_envelope)   # FIX-3 relay2")


def main():
    src = io.open(SRC, encoding='utf-8').read()
    cur = hashlib.sha256(src.encode('utf-8')).hexdigest()
    print('  baseline sha256 =', cur)
    if cur != BASE_SHA:
        print('  !! ABORT: baseline mismatch (expected %s)' % BASE_SHA)
        return 2
    if 'FIX-3 relay2' in src:
        print('  already applied')
        return 0
    for name, old in (('v1', OLD1), ('relay2', OLD2)):
        n = src.count(old)
        print('  anchor %-7s occurrences = %d' % (name, n))
        if n != 1:
            print('  !! ABORT: expected exactly 1')
            return 3
    src = src.replace(OLD1, NEW1, 1).replace(OLD2, NEW2, 1)
    import ast
    try:
        ast.parse(src)
    except SyntaxError as e:
        print('  !! ABORT syntax:', e)
        return 4
    io.open(SRC, 'w', encoding='utf-8').write(src)
    out = src.encode('utf-8')
    print('  patched bytes  =', len(out))
    print('  patched sha256 =', hashlib.sha256(out).hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
