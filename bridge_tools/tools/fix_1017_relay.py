#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BAPATCH-1017RELAY v1：把 Account_LoginSync(1017/1019) 从"桥桩"改为"转发 Shittim"。
独立开关 /www/wwwroot/bapatch/cn_1017_relay.txt（1=转发，0/缺失=维持桩）。
"""
import hashlib, io, sys

SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
BASE_SHA = '4862500960fe6f5d70188ff7390d14362e8ae50d77d4e778e9d0264c45a46aaf'

BLOCK = '''# >>> BAPATCH-1017RELAY v1 BEGIN >>>
# Account_LoginSync：开关开时改走 relay2 → Shittim 真数据（不再用 gen1017 桩）。
# 开关：/www/wwwroot/bapatch/cn_1017_relay.txt   1/on/true/yes = 转发；0/缺失 = 维持桩（fail-safe）
RELAY1017_SWITCH = 'cn_1017_relay.txt'
RELAY1017_NAME = 'Account_LoginSync'
RELAY1017_SHITTIM_NUM = 1019        # Shittim 枚举里的真实编号
RELAY1017_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')


def relay1017_on():
    for d in RELAY1017_DIRS:
        try:
            with open(os.path.join(d, RELAY1017_SWITCH), 'r') as fh:
                return fh.read().strip().lower() in ('1', 'on', 'true', 'yes')
        except Exception:
            continue
    return False


def relay1017_fix_num(name, num, req, rec=None):
    """把 LoginSync 的协议号修正成 Shittim 的 1019（若客户端发 1017 也不怕）。"""
    try:
        if not relay1017_on():
            return num
        if name != RELAY1017_NAME:
            return num
        if isinstance(num, int) and num == RELAY1017_SHITTIM_NUM:
            return num
        if isinstance(req, dict):
            req['Protocol'] = RELAY1017_SHITTIM_NUM
        if isinstance(rec, dict):
            rec['relay1017_num_from'] = num
            rec['relay1017_num_to'] = RELAY1017_SHITTIM_NUM
        return RELAY1017_SHITTIM_NUM
    except Exception:
        return num

# <<< BAPATCH-1017RELAY v1 END <<<
'''

# ① rl2_route 的 skip-name 判断：开关开时放行 Account_LoginSync
SKIP_OLD = """    if isinstance(name, str) and name in RL2_SKIP_NAMES:
        rec['relay2_fallthrough'] = 'skip-name'
        return None"""
SKIP_NEW = """    if isinstance(name, str) and name in RL2_SKIP_NAMES:
        # BAPATCH-1017RELAY v1: LoginSync 开关打开时不吃 skip
        if (name == RELAY1017_NAME and relay1017_on()):
            rec['relay1017_skip_bypass'] = True
        else:
            rec['relay2_fallthrough'] = 'skip-name'
            return None"""

# ② _rl2_relay_once 里、RL2_HANDLED 检查之前修正协议号
NUM_OLD = """    if num in RL2_HANDLED:
        # 1002/1014/3/1005/1017/24000/26000/4000/90004 … 有真生成器或专分支：绝不抢
        rec['relay2_fallthrough'] = 'handled-%d' % num
        return None"""
NUM_NEW = """    # BAPATCH-1017RELAY v1: 协议号对齐 Shittim（1017→1019）
    num = relay1017_fix_num(name, num, req, rec)
    rec['relay2_num'] = num
    if num in RL2_HANDLED:
        # 1002/1014/3/1005/1017/24000/26000/4000/90004 … 有真生成器或专分支：绝不抢
        rec['relay2_fallthrough'] = 'handled-%d' % num
        return None"""


def main():
    src = io.open(SRC, encoding='utf-8').read()
    cur = hashlib.sha256(src.encode('utf-8')).hexdigest()
    print('  baseline sha256 =', cur)
    if cur != BASE_SHA:
        print('  !! ABORT baseline mismatch')
        return 2
    if 'BAPATCH-1017RELAY' in src:
        print('  already applied')
        return 0
    for nm, old in (('SKIP', SKIP_OLD), ('NUM', NUM_OLD)):
        c = src.count(old)
        print('  anchor %-5s occurrences = %d' % (nm, c))
        if c != 1:
            print('  !! ABORT anchor not unique')
            return 3
    mark = "# <<< BAPATCH-BILLINGBLOCK v1 END <<<\n"
    if src.count(mark) != 1:
        print('  !! ABORT billingblock end marker =', src.count(mark))
        return 4
    src = src.replace(mark, mark + '\n' + BLOCK, 1)
    src = src.replace(SKIP_OLD, SKIP_NEW, 1)
    src = src.replace(NUM_OLD, NUM_NEW, 1)

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
