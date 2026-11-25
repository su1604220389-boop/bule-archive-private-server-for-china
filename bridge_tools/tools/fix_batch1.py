#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BATCH-1 three-in-one bridge patch.

1) BAPATCH-DEVID v1  - feed DevId/DeviceUniqueId into account_service (multi-player split)
2) BAPATCH-90011 v1  - Shop_ListTutorialGacha(90011) into RL2_HANDLED (stub instead of relay)
3) BAPATCH-DEDUP v1  - order dedupe for Billing_TransactionEndByYostar(29001)

Independent switches, base-sha gate, AST gate, idempotent.
"""
import hashlib
import io
import sys

SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
BASE_SHA = 'ade3917cab391de3d782decbdceda1d71556a9ee7e2487be869afebcd2f73807'

BLOCK = '''# >>> BAPATCH-DEVID v1 BEGIN >>>
DEVID_SWITCH = 'cn_devid.txt'
DEVID_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')


def devid_on():
    for d in DEVID_DIRS:
        try:
            with open(os.path.join(d, DEVID_SWITCH), 'r') as fh:
                return fh.read().strip().lower() in ('1', 'on', 'true', 'yes')
        except Exception:
            continue
    return False


def devid_stash(rec, d):
    try:
        if not devid_on() or not isinstance(d, dict) or not isinstance(rec, dict):
            return
        dv = d.get('DevId')
        du = d.get('DeviceUniqueId')
        if isinstance(dv, str) and dv.strip():
            rec['req_DevId'] = dv.strip()
        if isinstance(du, str) and du.strip():
            rec['req_DeviceUniqueId'] = du.strip()
    except Exception:
        pass

# <<< BAPATCH-DEVID v1 END <<<
'''

DEDUP_BLOCK = '''# >>> BAPATCH-DEDUP v1 BEGIN >>>
DEDUP_SWITCH = 'cn_dedup.txt'
DEDUP_WINDOW_FILE = 'cn_dedup_window.txt'
DEDUP_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')
DEDUP_NAMES = frozenset(('Billing_TransactionEndByYostar',))
_DEDUP_CACHE = {}


def dedup_on():
    for d in DEDUP_DIRS:
        try:
            with open(os.path.join(d, DEDUP_SWITCH), 'r') as fh:
                return fh.read().strip().lower() in ('1', 'on', 'true', 'yes')
        except Exception:
            continue
    return False


def dedup_window():
    for d in DEDUP_DIRS:
        try:
            v = int(open(os.path.join(d, DEDUP_WINDOW_FILE)).read().strip())
            return v if v > 0 else 900
        except Exception:
            continue
    return 900


def dedup_key(name, rec):
    if not isinstance(rec, dict):
        return None
    frag = (rec.get('req_frag_head') or '').strip()
    if not frag:
        return None
    import hashlib as _h
    body = frag.lstrip(',').replace('"Hash":', '"__H__":')
    return '%s|frag=%s' % (name, _h.sha256(body.encode('utf-8', 'replace')).hexdigest()[:32])


def dedup_lookup(key):
    if not key:
        return None
    ent = _DEDUP_CACHE.get(key)
    if not ent:
        return None
    ts, payload = ent
    if (time.time() - ts) > dedup_window():
        _DEDUP_CACHE.pop(key, None)
        return None
    return payload


def dedup_store(key, payload):
    if not key:
        return
    now = time.time()
    if len(_DEDUP_CACHE) > 4096:
        for k in [k for k, (ts, _) in _DEDUP_CACHE.items() if now - ts > dedup_window()]:
            _DEDUP_CACHE.pop(k, None)
    _DEDUP_CACHE[key] = (now, payload)


def dedup_replay(name, rec):
    try:
        if not dedup_on() or name not in DEDUP_NAMES:
            return None
        key = dedup_key(name, rec)
        if not key:
            return None
        hit = dedup_lookup(key)
        if isinstance(rec, dict):
            rec['dedup_key'] = key
            rec['dedup_hit'] = hit is not None
        return hit
    except Exception:
        return None

# <<< BAPATCH-DEDUP v1 END <<<
'''

REQ_OLD = """    try:
        return json.loads(body)
    except Exception:
        return {}


def acct_apply_to_auth(inner, rec):"""
REQ_NEW = """    try:
        _d = json.loads(body)
    except Exception:
        return {}
    devid_stash(rec, _d)
    return _d if isinstance(_d, dict) else {}


def acct_apply_to_auth(inner, rec):"""

FB_OLD = """            req = {'DevId': rec.get('req_DevId') or '', 'Token': rec.get('req_Token') or ''}"""
FB_NEW = """            req = {'DevId': rec.get('req_DevId') or '',
                   'DeviceUniqueId': rec.get('req_DeviceUniqueId') or '',
                   'Token': rec.get('req_Token') or ''}"""

HANDLED_OLD = """RL2_HANDLED = frozenset((1002, 1014, 1000, 1009, 1012, 1019, 2001, 3, 1017,   # FIX-2: 1005 已移出，改走转发
                         24000, 26000, 4000, 90004))"""
HANDLED_NEW = """RL2_HANDLED = frozenset((1002, 1014, 1000, 1009, 1012, 1019, 2001, 3, 1017,   # FIX-2: 1005 已移出，改走转发
                         24000, 26000, 4000, 90004,
                         90011))   # BAPATCH-90011 v1: Shop_ListTutorialGacha (no Shittim enum/handler)"""

HOOK_OLD = """        # BAPATCH-BILLINGBLOCK v1: 付费礼包止血（开关开时直接拒绝，不转发、不拉 SDK）
        _bb = billing_block_response(self, name, rec)
        if _bb is not None:
            return _bb"""
HOOK_NEW = HOOK_OLD + """

        # BAPATCH-DEDUP v1: order dedupe (replay cached response instead of relaying again)
        _dd = dedup_replay(name, rec)
        if _dd is not None:
            return _dd"""


def main():
    src = io.open(SRC, encoding='utf-8').read()
    cur = hashlib.sha256(src.encode('utf-8')).hexdigest()
    print('  baseline sha256 =', cur)
    if cur != BASE_SHA:
        print('  !! ABORT baseline mismatch')
        return 2
    if 'BAPATCH-DEVID' in src or 'BAPATCH-DEDUP' in src:
        print('  already applied')
        return 0
    for nm, old in (('REQ', REQ_OLD), ('FB', FB_OLD), ('HANDLED', HANDLED_OLD), ('HOOK', HOOK_OLD)):
        c = src.count(old)
        print('  anchor %-8s occurrences = %d' % (nm, c))
        if c != 1:
            print('  !! ABORT anchor not unique')
            return 3
    mark = "# <<< BAPATCH-1017RELAY v1 END <<<\n"
    if src.count(mark) != 1:
        print('  !! ABORT 1017relay marker =', src.count(mark))
        return 4
    src = src.replace(mark, mark + '\n' + BLOCK + '\n' + DEDUP_BLOCK, 1)
    src = src.replace(REQ_OLD, REQ_NEW, 1)
    src = src.replace(FB_OLD, FB_NEW, 1)
    src = src.replace(HANDLED_OLD, HANDLED_NEW, 1)
    src = src.replace(HOOK_OLD, HOOK_NEW, 1)

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
