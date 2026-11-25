#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FIX-6 / BAPATCH-NAMETOKEN v1
用 b32md5(真名) 反查表把客户端 token 解析成权威协议名（§0 优先级最高）。
开关 cn_nametoken.txt（默认 0=关）。
"""
import hashlib, io, sys

SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
BASE_SHA = '128c6ba9bec71590a6443610a3814cfb8d56f0a03b973241e54dabf1bde405d4'

BLOCK = '''# >>> BAPATCH-NAMETOKEN v1 BEGIN >>> (deploy/fix6_nametoken.py)
# 客户端发的外层 token = base32(md5(UTF-16LE(真名)))，所以 token->真名 是可验证的权威映射。
# 本块从 shittim_name_tokens.json（501 条，源自 Schale Protocol enum）建表，
# 在 name_fix_resolve 里作为 §0 最高优先级；避免"路径机械转换"把名字大小写弄错
# （实测 /api/campaign/entermainstage 曾被转成 Campaign_Entermainstage，真名是 Campaign_EnterMainStage）。
NAMETOKEN_SWITCH_FILE = 'cn_nametoken.txt'
NAMETOKEN_FALLBACK_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')
NAMETOKEN_MAP_FILE = '/www/wwwroot/bapatch/tools/shittim_name_tokens.json'
_NAMETOKEN_MAP = None


def nametoken_on(base=None):
    dirs = []
    if base:
        dirs.append(base)
    dirs.extend(NAMETOKEN_FALLBACK_DIRS)
    for d in dirs:
        try:
            with open(os.path.join(d, NAMETOKEN_SWITCH_FILE), 'r') as fh:
                return fh.read().strip().lower() in ('1', 'on', 'true', 'yes')
        except Exception:
            continue
    return False


def nametoken_map():
    global _NAMETOKEN_MAP
    if _NAMETOKEN_MAP is None:
        try:
            with open(NAMETOKEN_MAP_FILE, 'r', encoding='utf-8') as fh:
                _NAMETOKEN_MAP = json.load(fh)
        except Exception:
            _NAMETOKEN_MAP = {}
    return _NAMETOKEN_MAP


def nametoken_resolve(tok):
    """token -> 权威协议名；开关关/查不到 -> None。"""
    if not isinstance(tok, str) or not tok:
        return None
    try:
        if not nametoken_on():
            return None
        return nametoken_map().get(tok)
    except Exception:
        return None

# <<< BAPATCH-NAMETOKEN v1 END <<<
'''

DOC_ANCHOR = '''def name_fix_resolve(proto_str, rec=None):
    """token -> 名字。永不返回 None/'Unknown'（除非连路径都没有）。"""
    nm = None
'''

DOC_NEW = '''def name_fix_resolve(proto_str, rec=None):
    """token -> 名字。永不返回 None/'Unknown'（除非连路径都没有）。"""
    # BAPATCH-NAMETOKEN v1 §0: token 反查（权威，优先于一切猜测）
    try:
        _tn = nametoken_resolve(proto_str)
        if _tn:
            if isinstance(rec, dict):
                rec['name_fix_src'] = 'token-authoritative'
            return _tn
    except Exception:
        pass
    nm = None
'''


def main():
    src = io.open(SRC, encoding='utf-8').read()
    cur = hashlib.sha256(src.encode('utf-8')).hexdigest()
    print('  baseline sha256 =', cur)
    if cur != BASE_SHA:
        print('  !! ABORT baseline mismatch')
        return 2
    if 'BAPATCH-NAMETOKEN' in src:
        print('  already applied')
        return 0
    mark = "# <<< BAPATCH-NAME-FIX v1 END <<<\n"
    print('  anchor NAME-FIX-END =', src.count(mark))
    print('  anchor DOC           =', src.count(DOC_ANCHOR))
    if src.count(mark) != 1 or src.count(DOC_ANCHOR) != 1:
        print('  !! ABORT anchor not unique')
        return 3
    src = src.replace(mark, mark + '\n' + BLOCK, 1)
    src = src.replace(DOC_ANCHOR, DOC_NEW, 1)
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
