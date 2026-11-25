#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BAPATCH-NAME-FIX v1 -- 单变量修复：外层 protocol 永远不再输出 'Unknown'。

基线：/www/wwwroot/bapatch/tools/account_auth_probe.py
      141066 B / sha256 aefb38a8ad8c2a0a47d20e7a0d9995024f7d532f119de491e74125d076642b65

做两件事（都包在 BAPATCH-NAME-FIX 标记里，可整块摘除）：
  1) 插入 NAME_FIX_BY_PATH 表 + name_fix_resolve() 助手
  2) 把 L1688 的 `name = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(proto_str)`
     换成 `name = name_fix_resolve(proto_str, rec)`
"""
import hashlib, io, sys

SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
BASE_SHA = 'aefb38a8ad8c2a0a47d20e7a0d9995024f7d532f119de491e74125d076642b65'

BLOCK = '''# >>> BAPATCH-NAME-FIX v1 BEGIN >>> (deploy/fix_name_unknown.py)
# 修复：外层信封的 protocol 字段以前在名字查不到时会写成 'Unknown'，客户端报 invalidprotocol。
# 根因：protocol_names.txt 里混进了 159 行与 BA 无关的名字（Redis ERR_* / IRC RPL_*），
#       真实协议名大多不在表里 -> NAME_TABLE.get(token) = None -> 'Unknown'。
# 对策：token 查不到时，按「请求路径 -> 官方 PascalCase 全名」兜底；再查不到就按路径
#       机械转成 Xxx_Yyy，**永不返回 'Unknown'/None**。
NAME_FIX_BY_PATH = {
    '/api/account/auth': 'Account_Auth',
    '/api/account/nickname': 'Account_Nickname',
    '/api/account/callname': 'Account_CallName',
    '/api/account/checknexon': 'Account_CheckNexon',
    '/api/account/loginsync': 'Account_LoginSync',
    '/api/account/gettutorial': 'Account_GetTutorial',
    '/api/account/settutorial': 'Account_SetTutorial',
    '/api/academy/getinfo': 'Academy_GetInfo',
    '/api/item/list': 'Item_List',
    '/api/networktime/sync': 'NetworkTime_Sync',
    '/api/contentsave/get': 'ContentSave_Get',
    '/api/management/data': 'Management_Data',
    '/api/shop/listtutorialgacha': 'Shop_ListTutorialGacha',
    '/api/mission/list': 'Mission_List',
    '/api/mission/guidemissionseasonlist': 'Mission_GuideMissionSeasonList',
    '/api/minigame/missionlist': 'MiniGame_MissionList',
    '/api/toast/list': 'Toast_List',
    '/api/scenario/skip': 'Scenario_Skip',
    '/api/scenario/select': 'Scenario_Select',
    '/api/event/rewardincrease': 'Event_RewardIncrease',
    '/api/opencondition/eventlist': 'OpenCondition_EventList',
    '/api/notification/eventcontentreddotcheck': 'Notification_EventContentReddotCheck',
    '/api/mail/check': 'Mail_Check',
    '/api/mail/list': 'Mail_List',
    '/api/mail/listsemipermanent': 'Mail_ListSemiPermanent',
    '/api/campaign/list': 'Campaign_List',
    '/api/campaign/entermainstagestrategyskip': 'Campaign_EnterMainStageStrategySkip',
    '/api/echelon/list': 'Echelon_List',
    '/api/echelon/save': 'Echelon_Save',
    '/api/clan/check': 'Clan_Check',
    '/api/friend/check': 'Friend_Check',
    '/api/billing/purchaselistbyyostar': 'Billing_PurchaseListByYostar',
}

NAME_FIX_BY_NUM = {
    1001: 'Account_Nickname', 1002: 'Account_Auth', 1005: 'Account_GetTutorial',
    1006: 'Account_SetTutorial', 1014: 'Account_CheckNexon', 1017: 'Account_LoginSync',
    4000: 'Item_List', 8000: 'Mission_List', 8006: 'Mission_GuideMissionSeasonList',
    9004: 'Management_Data', 90004: 'Management_Data', 90011: 'Shop_ListTutorialGacha',
    16000: 'Toast_List', 19003: 'Scenario_Skip', 19004: 'Scenario_Select',
    24000: 'Academy_GetInfo', 26000: 'ContentSave_Get', 35003: 'MiniGame_MissionList',
    25003: 'Event_RewardIncrease', 15002: 'OpenCondition_EventList',
    36001: 'Notification_EventContentReddotCheck',
}


def name_fix_from_path(path):
    """路径兜底：/api/shop/listtutorialgacha -> 'Shop_ListTutorialGacha'（机械转换）。"""
    if not isinstance(path, str) or not path:
        return None
    p = path.split('?', 1)[0].strip('/')
    parts = [x for x in p.split('/') if x]
    if parts and parts[0].lower() == 'api':
        parts = parts[1:]
    if not parts:
        return None
    out = []
    for seg in parts:
        seg = ''.join(ch for ch in seg if ch.isalnum())
        if not seg:
            continue
        out.append(seg[0].upper() + seg[1:])
    return '_'.join(out) or None


def name_fix_resolve(proto_str, rec=None):
    """token -> 名字。永不返回 None/'Unknown'（除非连路径都没有）。"""
    nm = None
    try:
        nm = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(proto_str)
    except Exception:
        nm = None
    if nm and nm != 'Unknown':
        return nm
    path = None
    if isinstance(rec, dict):
        path = rec.get('path') or rec.get('request_path')
        if not path:
            rl = rec.get('reqline') or ''
            if isinstance(rl, str) and ' ' in rl:
                bits = rl.split()
                if len(bits) >= 2:
                    path = bits[1]
    if isinstance(path, str):
        key = path.split('?', 1)[0].rstrip('/').lower()
        nm = NAME_FIX_BY_PATH.get(key)
        if nm:
            if isinstance(rec, dict):
                rec['name_fix_src'] = 'path-table'
            return nm
    num = None
    if isinstance(rec, dict):
        for k in ('gen_protocol', 'fallback_protocol', 'proto_int'):
            v = rec.get(k)
            if isinstance(v, int) and v > 0:
                num = v
                break
            if isinstance(v, str) and v.isdigit():
                num = int(v)
                break
    if num is not None:
        nm = NAME_FIX_BY_NUM.get(num)
        if nm:
            if isinstance(rec, dict):
                rec['name_fix_src'] = 'num-table'
            return nm
    nm = name_fix_from_path(path if isinstance(path, str) else None)
    if nm:
        if isinstance(rec, dict):
            rec['name_fix_src'] = 'path-derived'
        return nm
    if isinstance(rec, dict):
        rec['name_fix_src'] = 'none'
    return nm

# <<< BAPATCH-NAME-FIX v1 END <<<


'''

OLD_LINE = "        name = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(proto_str)"
NEW_LINE = "        name = name_fix_resolve(proto_str, rec)   # BAPATCH-NAME-FIX v1"

ANCHOR_TAIL = "    'P3OMQZD2FXV7XXEGA7ETCXIJ4Q': 'Account_LoginSync',\n}\n"


def main():
    src = io.open(SRC, encoding='utf-8').read()
    cur = hashlib.sha256(src.encode('utf-8')).hexdigest()
    print('  baseline sha256 =', cur)
    if cur != BASE_SHA:
        print('  !! ABORT: baseline mismatch, expected', BASE_SHA)
        return 2
    if 'BAPATCH-NAME-FIX' in src:
        print('  already patched, nothing to do')
        return 0
    if src.count(ANCHOR_TAIL) != 1:
        print('  !! ABORT: EXTRA_TOKENS anchor count =', src.count(ANCHOR_TAIL))
        return 3
    if src.count(OLD_LINE) != 1:
        print('  !! ABORT: name lookup line count =', src.count(OLD_LINE))
        return 4

    src = src.replace(ANCHOR_TAIL, ANCHOR_TAIL + BLOCK, 1)
    src = src.replace(OLD_LINE, NEW_LINE, 1)

    import ast
    try:
        ast.parse(src)
    except SyntaxError as e:
        print('  !! ABORT: syntax error after patch:', e)
        return 5

    io.open(SRC, 'w', encoding='utf-8').write(src)
    out = src.encode('utf-8')
    print('  patched bytes  =', len(out))
    print('  patched sha256 =', hashlib.sha256(out).hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
