#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FIX-5b / BAPATCH-PROTONUM v1
请求出方向：client num -> Shittim num（按名字查表）
响应回方向：Shittim num -> client num（改回客户端原号）
独立开关 cn_protonum_remap.txt（默认 0=关）。
"""
import hashlib, io, sys

SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
BASE_SHA = '128c6ba9bec71590a6443610a3814cfb8d56f0a03b973241e54dabf1bde405d4'

BLOCK = '''# >>> BAPATCH-PROTONUM v1 BEGIN >>> (deploy/fix5b_protonum.py)
# 背景：客户端编号与 Shittim 枚举编号并非全同（实测 1017: client=Account_LoginSync，
#       Shittim 的 Account_LoginSync=1019、1017=Account_DismissRepurchasablePopup）。
# 做法：① 请求出方向按名字把 Protocol 换成 Shittim 编号；② 响应回方向改回客户端原号。
# 表来自 Schale/MX/NetworkProtocol/ProtocolData.cs（501 条），由补丁时生成的 json 提供。
# 开关 cn_protonum_remap.txt: 1/on/true/yes = 开；0/缺失 = 关（fail-safe）。
PROTONUM_SWITCH_FILE = 'cn_protonum_remap.txt'
PROTONUM_FALLBACK_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')
PROTONUM_MAP_FILE = '/www/wwwroot/bapatch/tools/shittim_protocol_map.json'
_PROTONUM_MAP = None


def protonum_on(base=None):
    dirs = []
    if base:
        dirs.append(base)
    dirs.extend(PROTONUM_FALLBACK_DIRS)
    for d in dirs:
        try:
            with open(os.path.join(d, PROTONUM_SWITCH_FILE), 'r') as fh:
                v = fh.read().strip().lower()
            return v in ('1', 'on', 'true', 'yes')
        except Exception:
            continue
    return False


def protonum_map():
    global _PROTONUM_MAP
    if _PROTONUM_MAP is None:
        try:
            with open(PROTONUM_MAP_FILE, 'r', encoding='utf-8') as fh:
                _PROTONUM_MAP = json.load(fh)
        except Exception:
            _PROTONUM_MAP = {}
    return _PROTONUM_MAP


def protonum_for_shittim(name, client_num, rec=None):
    """返回应发给 Shittim 的 Protocol 值；查不到就原样返回 client_num。"""
    try:
        if not protonum_on():
            if isinstance(rec, dict):
                rec['protonum_off'] = True
            return client_num
        if not isinstance(name, str) or not name:
            if isinstance(rec, dict):
                rec['protonum_skip'] = 'no-name'
            return client_num
        n = protonum_map().get(name)
        if not isinstance(n, int):
            if isinstance(rec, dict):
                rec['protonum_skip'] = 'name-not-in-shittim-enum'
            return client_num
        if isinstance(rec, dict):
            rec['protonum_req_from'] = client_num
            rec['protonum_req_to'] = n
            rec['protonum_remapped'] = (n != client_num)
        return n
    except Exception as e:
        if isinstance(rec, dict):
            rec['protonum_err'] = repr(e)
        return client_num

# <<< BAPATCH-PROTONUM v1 END <<<
'''

REQ_ANCHOR = """    if num in RL2_HANDLED:
        # 1002/1014/3/1005/1017/24000/26000/4000/90004 … 有真生成器或专分支：绝不抢
        rec['relay2_fallthrough'] = 'handled-%d' % num
        return None
"""

REQ_NEW = """    if num in RL2_HANDLED:
        # 1002/1014/3/1005/1017/24000/26000/4000/90004 … 有真生成器或专分支：绝不抢
        rec['relay2_fallthrough'] = 'handled-%d' % num
        return None
    # BAPATCH-PROTONUM v1: 出方向按名字换成 Shittim 编号（客户端号 != Shittim 号时才有差异，如 1017->1019）
    try:
        _pn = protonum_for_shittim(name, num, rec)
        if _pn != num:
            req['Protocol'] = _pn
            rec['relay2_protocol_remapped'] = _pn
    except Exception as _pne:
        rec['protonum_err'] = repr(_pne)
"""

RESP_ANCHOR = """    out = None
    # 注意：bridge 的 _cn_envelope(proto_name, ...) 会自己算 base32(md5(protocol_name))"""

RESP_NEW = """    # BAPATCH-PROTONUM v1: 回方向改回客户端原号，避免客户端 invalidprotocol
    try:
        if protonum_on() and isinstance(obj, dict) and isinstance(num, int) and obj.get('Protocol') != num:
            rec['protonum_resp_from'] = obj.get('Protocol')
            rec['protonum_resp_to'] = num
            obj['Protocol'] = num
    except Exception as _pnr:
        rec['protonum_err'] = repr(_pnr)
    out = None
    # 注意：bridge 的 _cn_envelope(proto_name, ...) 会自己算 base32(md5(protocol_name))"""


def main():
    src = io.open(SRC, encoding='utf-8').read()
    cur = hashlib.sha256(src.encode('utf-8')).hexdigest()
    print('  baseline sha256 =', cur)
    if cur != BASE_SHA:
        print('  !! ABORT baseline mismatch')
        return 2
    if 'BAPATCH-PROTONUM' in src:
        print('  already applied')
        return 0
    for nm, anch in (('REQ', REQ_ANCHOR), ('RESP', RESP_ANCHOR)):
        c = src.count(anch)
        print('  anchor %-5s occurrences = %d' % (nm, c))
        if c != 1:
            print('  !! ABORT anchor not unique')
            return 3
    # 插块：放到 name_fix_resolve 之后（BAPATCH-NAME-FIX END 处）
    mark = "# <<< BAPATCH-NAME-FIX v1 END <<<\n"
    if src.count(mark) != 1:
        print('  !! ABORT NAME-FIX end marker not unique')
        return 4
    src = src.replace(mark, mark + '\n' + BLOCK, 1)
    src = src.replace(REQ_ANCHOR, REQ_NEW, 1)
    src = src.replace(RESP_ANCHOR, RESP_NEW, 1)

    import ast
    try:
        ast.parse(src)
    except SyntaxError as e:
        print('  !! ABORT syntax:', e)
        return 5
    io.open(SRC, 'w', encoding='utf-8').write(src)
    out = src.encode('utf-8')
    print('  patched bytes  =', len(out))
    print('  patched sha256 =', hashlib.sha256(out).hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
