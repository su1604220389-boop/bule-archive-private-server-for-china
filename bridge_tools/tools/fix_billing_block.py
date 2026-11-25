#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BILLING-BLOCK v1：拦住 Billing_TransactionStartByYostar(29000)，防止拉起真实支付。
独立开关 /www/wwwroot/bapatch/cn_billing_block.txt（1=拦，0/缺失=放行）。
"""
import hashlib, io, sys

SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
BASE_SHA = '2475f231f196b4770a59e2376c6fda02fc8d29cdbca880a12d12603ffc400047'

BLOCK = '''# >>> BAPATCH-BILLINGBLOCK v1 BEGIN >>>
# 目的：拦住 Billing_TransactionStartByYostar(29000)，让客户端拉不起 Yostar 支付 SDK，
#       避免用户点付费礼包时产生**真实支付**。
# 开关：/www/wwwroot/bapatch/cn_billing_block.txt   1/on/true/yes = 拦；0/缺失 = 放行（fail-open）
# 回滚：echo 0 > /www/wwwroot/bapatch/cn_billing_block.txt   （下一次请求即生效，无需重启）
BILLING_BLOCK_SWITCH = 'cn_billing_block.txt'
BILLING_BLOCK_NAME = 'Billing_TransactionStartByYostar'
BILLING_BLOCK_NUM = 29000
BILLING_BLOCK_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')


def billing_block_on():
    for d in BILLING_BLOCK_DIRS:
        try:
            with open(os.path.join(d, BILLING_BLOCK_SWITCH), 'r') as fh:
                return fh.read().strip().lower() in ('1', 'on', 'true', 'yes')
        except Exception:
            continue
    return False


def billing_block_response(handler, name, rec):
    """返回 (code, body, ctype) 或 None。"""
    try:
        if not billing_block_on():
            return None
        if name != BILLING_BLOCK_NAME:
            return None
        from datetime import datetime as _dt
        _now = _dt.now()
        _ticks = int((_now - _dt(1, 1, 1)).total_seconds()) * 10_000_000 + _now.microsecond * 10
        obj = {
            'Protocol': BILLING_BLOCK_NUM,
            'ErrorCode': 500,
            'ServerTimeTicks': _ticks,
        }
        if isinstance(rec, dict):
            rec['billing_blocked'] = True
            rec['billing_block_name'] = name
        return handler._cn_send_envelope(BILLING_BLOCK_NAME, obj, rec)
    except Exception as e:
        if isinstance(rec, dict):
            rec['billing_block_err'] = repr(e)
        return None

# <<< BAPATCH-BILLINGBLOCK v1 END <<<
'''

ANCHOR = "        name = name_fix_resolve(proto_str, rec)   # BAPATCH-NAME-FIX v1"
NEW = (ANCHOR + "\n"
       "        # BAPATCH-BILLINGBLOCK v1: 付费礼包止血（开关开时直接拒绝，不转发、不拉 SDK）\n"
       "        _bb = billing_block_response(self, name, rec)\n"
       "        if _bb is not None:\n"
       "            return _bb\n")


def main():
    src = io.open(SRC, encoding='utf-8').read()
    cur = hashlib.sha256(src.encode('utf-8')).hexdigest()
    print('  baseline sha256 =', cur)
    if cur != BASE_SHA:
        print('  !! ABORT baseline mismatch')
        return 2
    if 'BAPATCH-BILLINGBLOCK' in src:
        print('  already applied')
        return 0
    if src.count(ANCHOR) != 1:
        print('  !! ABORT anchor count =', src.count(ANCHOR))
        return 3
    mark = "# <<< BAPATCH-NAMETOKEN v1 END <<<\n"
    if src.count(mark) != 1:
        print('  !! ABORT NAMETOKEN end marker =', src.count(mark))
        return 4
    src = src.replace(mark, mark + '\n' + BLOCK, 1)
    src = src.replace(ANCHOR, NEW, 1)
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
