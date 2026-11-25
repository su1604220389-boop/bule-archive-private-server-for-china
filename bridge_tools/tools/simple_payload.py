# -*- coding: utf-8 -*-
"""simple_payload.py -- 1005 / 4000 / 26000 三个协议的载荷构造器（唯一真源）。

本文件有**两个消费者，读同一份源码**：

  1. `deploy/gen_simple.py`   -- import 使用，离线渲染 + spec_check 验收
  2. `deploy/patch_simple.py` -- --apply 时把本文件**逐字节原样内嵌**进
                                 account_auth_probe.py（bridge），不抄第二份

所以这里必须满足「能被原样贴进 bridge 的模块命名空间里」：
  * 不写 `from __future__ import ...`（不是文件首语句会 SyntaxError）
  * 不写 `if __name__ == '__main__':`（bridge 就是脚本，会被执行）
  * 只用标准库 json / base64 / hashlib / os / re / uuid / datetime
  * import 期不碰文件系统、不碰网络、不读任何仓库文件
  * 公共名字统一 `simple_*` / `SIMPLE_*` 前缀，避免和 bridge 现有全局撞名

三个协议的数据来源（逐条可查，见 TEST_SIMPLE.md §0）：

  1005 TutorialIds = []          <- initial_state_rules.json  q7_tutorials.initial.TutorialIds
  4000 ItemDBs     = 1 行加速券  <- initial_state_rules.json  server_apply_skeleton.ItemDBs[0]
                                    (Type=4 / UniqueId=2 / StackCount=5 / IsNew=true)
                                    UniqueId=2 -> ItemDBSchema.Id=2（1803 行，excel_field_map 134/134 verified）
  26000 HasValidData=false + 两个 null  <- official_spec.json 26000（官方 8 键，后 3 键就是这三个值）
"""

import base64
import hashlib
import json
import os
import re
import uuid

# ---------------------------------------------------------------- 常量
SIMPLE_PROTOCOLS = (1005, 4000, 26000)

# 外层信封的 protocol 名（官方抓包实测，三个都逐字对过：见 report\_tmp\official_decoded_201\*.plain）
SIMPLE_NAMES = {
    1005: 'Account_GetTutorial',
    4000: 'Item_List',
    26000: 'ContentSave_Get',
}

# 每个协议一个独立开关文件，内容 1=启用 0=停用（缺失 = 停用，fail-safe）
SIMPLE_SWITCH_FILES = {
    1005: 'cn_1005.txt',
    4000: 'cn_4000.txt',
    26000: 'cn_26000.txt',
}

# 开关查找顺序：bridge 所在目录（dirname(__file__)）-> 线上 tools/ -> 线上 bapatch/
SIMPLE_FALLBACK_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')

# 账号号：bridge 拿不到时用它（= 官方抓包那个号 / 本项目测试号）
SIMPLE_DEFAULT_ACCOUNT = 10015354380
SIMPLE_ACCOUNT_FILE = 'cn_simple_account.txt'
SIMPLE_TICKS_FILE = 'cn_simple_ticks.txt'

# 新号初始道具：(ParcelType, ItemDBSchema.Id, StackCount, IsNew)
#   来源 initial_state_rules.json -> q3_initial_items.initial.ItemDBs
#        = DefaultParcelExcelTable 里唯一一行 ParcelType=4(Item)、ParcelId=2(加速券)、ParcelAmount=5
#   注意：skeleton 里那行还带 IsLocked（schema_v2 的列），官方 4000 的 ItemDB 只有 5 个键，
#        没有 IsLocked -> 这里就不放进去（否则 spec_check 报「多键」FAIL）。
SIMPLE_INITIAL_ITEMS = ((4, 2, 5, True),)

# 新号初始教程进度 = 空（q7_tutorials.initial.TutorialIds = []）。
# 只给调试/复现官方样本用 --tutorial-ids 覆盖；bridge 永远发空。
SIMPLE_TUTORIAL_IDS = ()

# ParcelType 枚举：Item=4（q3 evidence：MX.Data.LocalizeEtcData.GetName(FlatData.ParcelType, ...)）
SIMPLE_PARCEL_ITEM = 4


# ---------------------------------------------------------------- 开关
def simple_switch_dirs():
    """开关文件的候选目录（有序）。"""
    out = []
    try:
        out.append(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        pass
    for d in SIMPLE_FALLBACK_DIRS:
        if d not in out:
            out.append(d)
    return out


def simple_read_switch(fn, base=None):
    """读一个开关文件；返回 (路径, 内容)。找不到返回 (None, None)。"""
    dirs = []
    if base:
        dirs.append(base)
    dirs.extend(simple_switch_dirs())
    for d in dirs:
        if not d:
            continue
        p = os.path.join(d, fn)
        try:
            with open(p, 'r') as fh:
                return p, fh.read().strip()
        except Exception:
            continue
    return None, None


def simple_switch_on(num, base=None):
    """该协议是否启用。缺失/读不到/内容不是真值 -> False（fail-safe：停用）。"""
    try:
        num = int(num)
    except Exception:
        return False
    fn = SIMPLE_SWITCH_FILES.get(num)
    if not fn:
        return False
    _p, v = simple_read_switch(fn, base)
    if v is None:
        return False
    return v.strip().lower() in ('1', 'on', 'true', 'yes')


def simple_wants(num, base=None):
    """协议号属于三件套且开关打开 —— 给 bridge 的分发处做前置判断（不解密、不构包）。"""
    try:
        num = int(num)
    except Exception:
        return False
    return num in SIMPLE_PROTOCOLS and simple_switch_on(num, base)


# ---------------------------------------------------------------- 基础值
def simple_ticks(mode='utc', now=None):
    """.NET ticks（100ns，自 0001-01-01）。

    官方实测：ServerTimeTicks 解出来 == UTC 墙钟（1005: 639304002559071160 -> 2026-11-16T04:30:55.9Z，
    抓包 meta.bj 也记 04:30:56.071），所以默认 utc。
    bridge 里其它老分支用的是 datetime.now()（本地时间），本文件不跟随它 —— 见 TEST_SIMPLE.md §5 WARN-4。
    """
    from datetime import datetime, timezone
    if now is None:
        if str(mode).lower() == 'local':
            now = datetime.now()
        else:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
    delta = now - datetime(1, 1, 1)
    return (delta.days * 86400 + delta.seconds) * 10000000 + delta.microseconds * 10


def simple_ticks_mode(base=None):
    _p, v = simple_read_switch(SIMPLE_TICKS_FILE, base)
    if v and v.strip().lower() == 'local':
        return 'local'
    return 'utc'


def simple_mxtoken(account_id):
    """由账号派生 64 字符 base64 MxToken（= specgen.Account.create 的同一公式，48 字节 sha384）。"""
    raw = hashlib.sha384(('ba-private-server:%d' % int(account_id)).encode('utf-8')).digest()
    return base64.b64encode(raw).decode('ascii')


def simple_item_server_id(account_id, index=1):
    """道具的 ServerId = account_id * 100000 + 20000 + 序号（kind=2 道具）。

    与 work/ba/server/prototype/specgen.py 的 Account.obj_id(2, i) 同一公式，
    保证 1017 的编队/角色 ServerId 与本协议的道具 ServerId 用同一套号段、多账号共库不撞号。
    """
    return int(account_id) * 100000 + 20000 + int(index)


def simple_item_rows(account_id):
    rows = []
    for i, (ptype, uid, cnt, isnew) in enumerate(SIMPLE_INITIAL_ITEMS):
        rows.append({
            'Type': int(ptype),
            'ServerId': simple_item_server_id(account_id, i + 1),
            'UniqueId': int(uid),
            'StackCount': int(cnt),
            'IsNew': bool(isnew),
        })
    return rows


# ---------------------------------------------------------------- 三个载荷
def simple_build(num, account_id=None, mxtoken=None, rid=None, ticks=None, tutorial_ids=None):
    """构造协议 num 的完整响应（键序 = 官方 top_key_order）。"""
    num = int(num)
    if account_id is None:
        account_id = SIMPLE_DEFAULT_ACCOUNT
    account_id = int(account_id)
    if mxtoken is None:
        mxtoken = simple_mxtoken(account_id)
    if ticks is None:
        ticks = simple_ticks()
    if rid is None:
        rid = str(uuid.uuid4())

    if num == 1005:
        prog = SIMPLE_TUTORIAL_IDS if tutorial_ids is None else tutorial_ids
        return {
            'Protocol': 1005,
            'SessionKey': {'AccountServerId': account_id, 'MxToken': mxtoken},
            'ServerTimeTicks': int(ticks),
            'ServerNotification': 0,
            'RequestId': rid,
            # 进度表：新号一条教程都没播过 -> 空
            'TutorialIds': [int(x) for x in prog],
        }
    if num == 4000:
        return {
            'Protocol': 4000,
            'SessionKey': {'AccountServerId': account_id, 'MxToken': mxtoken},
            'ServerTimeTicks': int(ticks),
            'ServerNotification': 0,
            'RequestId': rid,
            'ItemDBs': simple_item_rows(account_id),
            'ExpiryItemDBs': [],
        }
    if num == 26000:
        return {
            'Protocol': 26000,
            'SessionKey': {'AccountServerId': account_id, 'MxToken': mxtoken},
            'ServerTimeTicks': int(ticks),
            'ServerNotification': 0,
            'RequestId': rid,
            'HasValidData': False,
            'ContentSaveDB': None,
            'EventContentChangeDB': None,
        }
    raise ValueError('simple_payload 不支持协议 %r' % (num,))


def simple_payload_json(num, **kw):
    """紧凑 JSON 字符串（= 真正进 packet 的那串字节）。"""
    return json.dumps(simple_build(num, **kw), ensure_ascii=False, separators=(',', ':'))


# ---------------------------------------------------------------- bridge 运行时
def simple_num_from_rec(rec):
    """从日志记录里恢复协议号：Hash >> 32（官方/客户端口径）。"""
    try:
        h = rec.get('req_Hash')
    except Exception:
        return None
    try:
        if isinstance(h, bool):
            return None
        if isinstance(h, int) and h > 0:
            return h >> 32
        if isinstance(h, str) and h.isdigit():
            return int(h) >> 32
    except Exception:
        pass
    return None


def simple_account_id(rec=None, base=None):
    """账号号优先级：SESSION.account_id -> 请求片段里的 AccountServerId -> 文件 -> 默认号。"""
    try:
        sess = globals().get('SESSION')
        aid = getattr(sess, 'account_id', None)
        if aid:
            return int(aid)
    except Exception:
        pass
    txt = ''
    if isinstance(rec, dict):
        for k in ('simple_frag', 'req_frag_head'):
            v = rec.get(k)
            if isinstance(v, str) and v:
                txt = v
                break
    if txt:
        m = re.search(r'"AccountServerId"\s*:\s*(\d+)', txt)
        if m:
            try:
                v = int(m.group(1))
            except Exception:
                v = 0
            if v > 0:
                return v
    _p, v = simple_read_switch(SIMPLE_ACCOUNT_FILE, base)
    if v:
        m = re.match(r'^\s*(\d{4,})\s*$', v)
        if m:
            return int(m.group(1))
    return SIMPLE_DEFAULT_ACCOUNT


def simple_mxtoken_from_frag(frag, account_id):
    """官方是「回显客户端的 MxToken」；拿不到就按账号派生（与 gen_simple 的默认值一致）。"""
    if isinstance(frag, str) and frag:
        m = re.search(r'"MxToken"\s*:\s*"([A-Za-z0-9+/=_-]{16,})"', frag)
        if m:
            return m.group(1)
    return simple_mxtoken(account_id)


def simple_route(rec, name=None, num=None, frag=None, send=None, base=None):
    """bridge 分发处调用。返回 (code, body, ctype) 表示已接管；返回 None 表示交回原兜底。

    send = cn_wire.wrap_response(protocol_name, inner_obj, requestid) -> (wire, plain, key)
    注入而不是直接 import，这样本文件离线（gen_simple / patch_simple --verify）也能跑同一条代码路径。
    """
    if num is None:
        num = simple_num_from_rec(rec)
    try:
        num = int(num)
    except Exception:
        return None
    if num not in SIMPLE_PROTOCOLS:
        return None
    if not simple_switch_on(num, base):
        if isinstance(rec, dict):
            rec['simple_off'] = num
        return None
    if send is None:
        return None

    if isinstance(rec, dict) and isinstance(frag, str) and frag:
        rec['simple_frag'] = frag[:2000]

    account_id = simple_account_id(rec, base)
    mxtoken = simple_mxtoken_from_frag(frag, account_id)
    ticks = simple_ticks(simple_ticks_mode(base))

    rid = None
    _pk = globals().get('pick_requestid')
    if callable(_pk):
        try:
            rid = _pk(rec)
        except Exception:
            rid = None
    if not rid:
        rid = str(uuid.uuid4())

    obj = simple_build(num, account_id, mxtoken, rid, ticks)
    proto_name = SIMPLE_NAMES[num]

    wire, plain, key = send(proto_name, obj, rid)

    if isinstance(rec, dict):
        rec['gen_kind'] = 'simple-%d' % num
        rec['fallback'] = 'simple-envelope'
        rec['simple_proto'] = num
        rec['simple_name'] = proto_name
        rec['simple_account_id'] = account_id
        rec['simple_keys'] = len(obj)
        rec['simple_item_rows'] = len(obj.get('ItemDBs') or [])
        rec['simple_tutorial_ids'] = len(obj.get('TutorialIds') or [])
        rec['simple_ticks'] = int(ticks)
        rec['enc_requestid'] = rid
        rec['enc_inner_keys'] = len(obj)
        rec['enc_plain_len'] = len(plain)
        rec['enc_body_len'] = len(wire)
        rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
    return 200, wire, 'text/plain; charset=utf-8'
