#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_24000_v3.py -- 在**正确基线**上把 24000 分支换成按账号动态生成。

为什么要 v3（v2 的错在哪）
==========================
v2 的锚点是 work/ba/server/_bridge_ref/account_auth_probe.py（46,568 B / 11-14 14:50）。
那是仓库里的**旧快照**，不是线上真跑的那份。线上真跑的是：

    work/ba/server/deploy/_baseline/account_auth_probe.py
    54,026 B / 1,245 行 / 11-14 15:38
    sha256 f94b4fa05d95d4c8719f5623322b75629b81eed59442370dd552db721437dbc9
    24000 分支：L787-812（26 行，E2 版）
        gen_kind = 'academy-24000-e2'
        ZoneScheduleGroupRecords：100+ 个 key（10000..26015 逐个给 []）
        AcademyLocationDBs：11 条（含 14 Trinity / 18 Shanhaijing）
        ZoneVisitCharacterDBs：list []（应为 dict）
        没有 SessionKey / RequestId / AcademyDB.AccountId
        AcadeyLocationDBs 每条没有 AccountId

v2 锚的旧快照里，24000 分支在 L685-695 左右（11 行简化版）。同样的替换逻辑打在
另一份代码上 ⇒ 行号、上下文、宿主符号全部对不上。

v3 只做两件事（都幂等）
=======================
1. 模块级插入/替换一个**托管块**（BEGIN/END 标记内）= gen24000.py 的引擎核（逐字内联）
   + 运行时适配层（取账号 / MxToken / RequestId、渲染、发送）。
   插入位置：`SESSION = Session()`（基线 L508）之后，避开全部现有代码。
2. 把 L787-812 整个 `if num == 24000:` 分支（26 行）换成 6 行调用。

目标文件其余部分一个字节都不动。连跑两次 sha256 不变。

7 处结构错误（report/102-最终修复方案.md §3）与 v3 的修法
========================================================
| # | 官方要求 | E2 版 | v3 |
|---|---|---|---|
| 1 | ZoneVisitCharacterDBs 是 map<string,array> | list `[]` | dict，71 个 zone key（字典序） |
| 2 | AcademyDB 有 AccountId | 无 | `AcademyDB.AccountId = account_id` |
| 3 | AcademyLocationDBs 每条有 AccountId | 无 | 每条 4 键 `{AccountId,LocationId,Rank,Exp}` |
| 4 | ZoneScheduleGroupRecords == {} | 100+ 个 key | 空字典 `{}` |
| 5 | SessionKey {AccountServerId, MxToken(64)} | 无 | 有，MxToken 64 字符 base64 |
| 6 | RequestId（值 = 外层 requestid） | 无 | uuid4，外层 requestid 与它**同值** |
| 7 | 无 MissionProgressDBs / EventMissionProgressDBDict / BattlePassMissionProgressDBDict / StaticOpenConditions | 4 个都在 | 一个都没有 |

正确结构（7 键，键序固定）：
    Protocol, SessionKey, ServerTimeTicks, ServerNotification, RequestId,
    AcademyDB{AccountId,LastUpdate,ZoneVisitCharacterDBs,ZoneScheduleGroupRecords},
    AcademyLocationDBs[]

写入前的 4 道闸（任何一道不过就 die，一个字节都不写）
====================================================
    闸 1  compile()                改后全文能被 CPython 编译
    闸 2  顶层撞名检查             托管块要新增的顶层名字与宿主现有名字无交集
    闸 3  引擎核同输入同字节       gen24000.py 与托管块内联核：同参数 → 同 dict / 同紧凑字节
                                   （附带：引擎 vs 官方抓包 packet 逐字节 11,685 B）
    闸 4  build+send+兜底三链自测  ① _ba24000_build 结构合法且 RequestId 每条新生成
                                   ② _ba24000_send 外层 requestid == 内层 RequestId
                                   ③ _ba24000_minimal 兜底也是合法 7 键结构
                                   三链都过 7 项结构核对

用法
====
    # 1) 看会改什么（不写文件；对 _baseline 也安全，因为只读）
    python work\\ba\\server\\deploy\\patch_24000_v3.py \\
        --target work\\ba\\server\\deploy\\_baseline\\account_auth_probe.py --dry-run

    # 2) 在临时副本上应用（推荐做法：先复制，再打）
    cp work\\ba\\server\\deploy\\_baseline\\account_auth_probe.py %TEMP%\\aap.py
    python work\\ba\\server\\deploy\\patch_24000_v3.py --target %TEMP%\\aap.py --apply

    # 3) 核对：打印分支 + 托管块 + 用真实账号渲染一次 + 7 项结构
    python work\\ba\\server\\deploy\\patch_24000_v3.py --target %TEMP%\\aap.py --verify

    # 4) 回滚：从备份恢复并校验 sha256（必须回到 f94b4fa0…）
    python work\\ba\\server\\deploy\\patch_24000_v3.py --target %TEMP%\\aap.py --rollback

    # 5) 线上（部署前置：gen24000.py 必须与补丁同目录）
    scp work/ba/server/deploy/gen24000.py work/ba/server/deploy/patch_24000_v3.py \\
        root@HOST:/www/wwwroot/bapatch/
    python3 /www/wwwroot/bapatch/patch_24000_v3.py --apply
    python3 /www/wwwroot/bapatch/patch_24000_v3.py --verify

守卫
====
* **拒绝写入** _baseline/ 与 _bridge_ref/（--dry-run / --verify 只读，允许）。
* --apply 只接受两种目标：sha256 == f94b4fa0…（已知基线）或已含 v3 托管块（幂等重跑）。
  其它一律 die（--allow-other-baseline 可越过），所以不会在 v2/292 补丁态上叠打。
* 不改任何别的文件；manifest 落在目标同级（或 bapatch/logs）目录。

退出码：0 = 成功 / 无事可做；1 = 校验失败；2 = 前置条件不满足（未写任何文件）
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import traceback
from datetime import datetime

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
DEPLOY_DIR = os.path.abspath(HERE)
SERVER_DIR = os.path.abspath(os.path.join(DEPLOY_DIR, '..'))
BASELINE_DIR = os.path.join(DEPLOY_DIR, '_baseline')
BASELINE_FILE = os.path.join(BASELINE_DIR, 'account_auth_probe.py')
BRIDGE_REF_DIR = os.path.join(SERVER_DIR, '_bridge_ref')

PATCH_NAME = '24000_v3'
ENGINE_FILE_NAME = 'gen24000.py'

# ---- 正确基线指纹（这三个数必须有同一个来源，改一个就得三个一起改）----
BASELINE_SHA256 = 'f94b4fa05d95d4c8719f5623322b75629b81eed59442370dd552db721437dbc9'
BASELINE_BYTES = 54026
BASELINE_LINES = 1245
# `if num == 24000:` 在基线里的位置（1-based，闭区间）与段长
BASELINE_BRANCH = (787, 812, 26)
BASELINE_E2_MARK = "academy-24000-e2"

# ---- 托管块标记（v3 自己的一套，不与 v2/292 混）----
BLOCK_BEGIN = '# ==== BEGIN 24000_v3 (managed block) ===='
BLOCK_END = '# ==== END 24000_v3 (managed block) ===='
BEGIN_V2 = '# ==== BEGIN 24000_v2 (managed block) ===='
BEGIN_292 = '# ==== BEGIN 292_24000_official (managed block) ===='

TARGET_CANDIDATES = (
    '/www/wwwroot/bapatch/tools/account_auth_probe.py',
    '/www/wwwroot/bapatch/account_auth_probe.py',
)
DEFAULT_MANIFEST_DIRS = ('/www/wwwroot/bapatch/logs',)
CONFIG_FILE = '/www/wwwroot/bapatch/academy_24000_config.json'

# 官方抓包（report/_tmp/official_decoded_201/01_24000_api_academy_getinfo.response.json）
EXPECTED_INNER_BYTES_OFFICIAL = 11685
FIXED_CASE = {
    'account_id': 10015354380,
    'mxtoken': '<REDACTED_TOKEN>',
    'request_id': '3770c1bc-a631-46fb-a9b6-0421ae2601fe',
    'ticks': 639304002548158993,
}

# 24,000 分支替换后的**全部内容**（6 行）。indent 由宿主那一行决定。
BRANCH_NEW = [
    'if num == 24000:',
    # frag 是 _generic_protocol_response 里解出来的请求明文。线上若 frag 不在作用域，
    # 退化成空串（账号改从 SESSION 取），绝不让 NameError 把连接变成 500。
    "    obj = _ba24000_build(frag if 'frag' in locals() else '', rec)",
    "    rec['gen_kind'] = 'academy-24000-v3'",
    "    rec['gen_v'] = 'v3'",
    "    rec['fallback'] = 'dynamic-24000'",
    "    return _ba24000_send(name or 'Academy_GetInfo', obj, rec)",
]

# 官方没有、E2 版误发的 4 个伪键（report/102 §3.5）
PSEUDO_KEYS = ('MissionProgressDBs', 'EventMissionProgressDBDict',
               'BattlePassMissionProgressDBDict', 'StaticOpenConditions')

DEFAULT_CONFIG = {
    'locations': None,
    'zone_scope': 'service',
    'last_update': None,
    'request_id_mode': 'fresh',
    'default_account_id': 0,
}


# ================================================================ 运行时适配层源码
# 这一段与引擎核一起被写进托管块。放补丁里（而不是 gen24000.py）是因为它依赖宿主的
# SESSION / cn_wire，属于"接线"，不属于"渲染引擎"。
ADAPTER_SRC = r'''
# ---------------------------------------------------------------- 24000 v3 运行时适配层
# 职责：① 取当前账号 / 会话 MxToken / RequestId；② 调引擎渲染；③ 把 inner RequestId 当外层 requestid 发出去。
# 铁律：本层任何函数都不允许把异常抛给调用方（抛了整条连接会变成 500，客户端拿不到 RequestId）。
_BA24000_CONFIG_FILE = '/www/wwwroot/bapatch/academy_24000_config.json'
_BA24000_DEFAULT_CONFIG = {
    'locations': None,
    'zone_scope': 'service',
    'last_update': None,
    'request_id_mode': 'fresh',
    'default_account_id': 0,
}
_BA24000_CFG = {'mtime': None, 'cfg': None}


def _ba24000_config(rec=None):
    """读 academy_24000_config.json（按 mtime 缓存）。文件不存在或坏掉都只回默认值，不抛。"""
    import json as _json
    import os as _os
    try:
        st = _os.stat(_BA24000_CONFIG_FILE)
    except Exception:
        return dict(_BA24000_DEFAULT_CONFIG)
    if _BA24000_CFG['cfg'] is not None and _BA24000_CFG['mtime'] == st.st_mtime:
        return _BA24000_CFG['cfg']
    cfg = dict(_BA24000_DEFAULT_CONFIG)
    try:
        with open(_BA24000_CONFIG_FILE, 'r') as f:
            data = _json.load(f)
        if isinstance(data, dict):
            for k in _BA24000_DEFAULT_CONFIG:
                if k in data:
                    cfg[k] = data[k]
        if rec is not None:
            rec['academy_cfg_file'] = _BA24000_CONFIG_FILE
            rec['academy_cfg_keys'] = sorted(cfg.keys())
    except Exception as e:
        if rec is not None:
            rec['academy_cfg_err'] = repr(e)
    _BA24000_CFG['cfg'] = cfg
    _BA24000_CFG['mtime'] = st.st_mtime
    return cfg


def _ba24000_fragment_text(frag):
    """请求片段可能多一层转义（客户端把整包 JSON 当字符串塞进来），统一还原。
    MxToken 是 base64、账号是数字，都不可能含反斜杠，所以整体替换是安全的。"""
    s = frag or ''
    try:
        if '\\"' in s:
            s = s.replace('\\"', '"')
    except Exception:
        pass
    return s


def _ba24000_find_int(text, key):
    import re as _re
    m = _re.search('"' + key + r'"\s*:\s*(\d+)', text or '')
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _ba24000_find_str(text, key):
    import re as _re
    m = _re.search('"' + key + r'"\s*:\s*"([^"]*)"', text or '')
    return m.group(1) if m else None


def _ba24000_session_key():
    """桥里缓存的会话（来自 CheckNexon 的真实 SessionKey，MxToken 是 64 字符 base64）。"""
    try:
        sk = getattr(SESSION, 'session_key', None)
    except Exception:
        return None
    return sk if isinstance(sk, dict) else None


def _ba24000_pick_account(text, cfg):
    """账号优先级：请求体 AccountId > 请求体 SessionKey.AccountServerId > 会话 > 配置兜底。"""
    aid = _ba24000_find_int(text, 'AccountId')
    if aid:
        return aid, 'request.AccountId'
    aid = _ba24000_find_int(text, 'AccountServerId')
    if aid:
        return aid, 'request.SessionKey.AccountServerId'
    try:
        if getattr(SESSION, 'account_id', None):
            return int(SESSION.account_id), 'session.account_id'
    except Exception:
        pass
    sk = _ba24000_session_key()
    if sk:
        try:
            return int(sk.get('AccountServerId')), 'session.session_key'
        except Exception:
            pass
    try:
        return int(cfg.get('default_account_id') or 0), 'config.default_account_id'
    except Exception:
        return 0, 'config.default_account_id'


def _ba24000_pick_token(text, cfg, account_id):
    """MxToken：请求体 > 会话 > 由账号派生（sha384->base64，恰好 64 字符，与官方同形）。"""
    tok = _ba24000_find_str(text, 'MxToken')
    if tok:
        return tok, 'request'
    sk = _ba24000_session_key()
    if sk and sk.get('MxToken'):
        return str(sk['MxToken']), 'session'
    import base64 as _b64
    import hashlib as _h
    try:
        raw = ('ba24000:%d' % int(account_id)).encode('utf-8')
    except Exception:
        raw = b'ba24000:0'
    return _b64.b64encode(_h.sha384(raw).digest()).decode('ascii'), 'generated'


def _ba24000_pick_request_id(rec, cfg):
    """RequestId：官方是**每条新生成**的 uuid4，外层 requestid 与它同值。
    echo 模式只是排查开关（把客户端请求头 REQUEST-ID 回显）——不是默认行为。"""
    import uuid as _uuid
    mode = str((cfg or {}).get('request_id_mode') or 'fresh')
    if mode == 'echo':
        hdrs = rec.get('headers') or {}
        for k in ('REQUEST-ID', 'Request-Id', 'request-id', 'Request-ID'):
            v = hdrs.get(k)
            if v and v != '-':
                rec['academy_rid_src'] = 'echo-http-header'
                return v
        rec['academy_rid_src'] = 'echo-no-header->uuid4'
        return str(_uuid.uuid4())
    rec['academy_rid_src'] = 'uuid4'
    return str(_uuid.uuid4())


def _ba24000_now_ticks():
    """服务器本地墙钟 -> .NET ticks。官方抓包实测 ticks 与抓包墙钟对齐（见 gen24000.py）。"""
    from datetime import datetime as _dtm
    return b24000_ticks(_dtm.now())


def _ba24000_build(frag, rec):
    """渲染 24000 inner。绝不抛异常。"""
    try:
        cfg = _ba24000_config(rec)
        text = _ba24000_fragment_text(frag)
        aid, asrc = _ba24000_pick_account(text, cfg)
        tok, tsrc = _ba24000_pick_token(text, cfg, aid)
        rid = _ba24000_pick_request_id(rec, cfg)
        ticks = _ba24000_now_ticks()
        last_update = cfg.get('last_update')
        obj = b24000_build(aid, tok, rid, ticks,
                           locations=cfg.get('locations') or None,
                           last_update=(str(last_update) if last_update else None),
                           zone_scope=(cfg.get('zone_scope') or 'service'))
        chk = b24000_check(obj)
        adb = obj.get('AcademyDB') or {}
        zv = adb.get('ZoneVisitCharacterDBs')
        rec['academy_account_id'] = aid
        rec['academy_account_src'] = asrc
        rec['academy_token_src'] = tsrc
        rec['academy_token_len'] = len(tok)
        rec['academy_token_is64'] = (len(tok) == 64)
        rec['academy_ticks'] = ticks
        rec['academy_request_id'] = rid
        rec['academy_last_update'] = adb.get('LastUpdate')
        rec['academy_top_keys'] = chk['top_keys']
        rec['academy_zv_keys'] = chk['zone_keys']
        rec['academy_zv_is_dict'] = isinstance(zv, dict)
        rec['academy_locations'] = chk['locations']
        rec['academy_inner_bytes'] = chk['inner_bytes']
        rec['academy_schedule_empty'] = (adb.get('ZoneScheduleGroupRecords') == {})
        rec['academy_no_pseudo_keys'] = not any(k in obj for k in (
            'MissionProgressDBs', 'EventMissionProgressDBDict',
            'BattlePassMissionProgressDBDict', 'StaticOpenConditions'))
        rec['academy_struct_ok'] = chk['ok']
        if chk['problems']:
            rec['academy_problems'] = list(chk['problems'])[:8]
        rec['academy_built'] = 'dynamic-v3'
        return obj
    except Exception as e:
        rec['academy_build_err'] = repr(e)
        rec['academy_built'] = 'fallback-v3'
        return _ba24000_minimal(rec)


def _ba24000_minimal(rec):
    """结构正确的兜底：7 键 / 71 zone / 1 条地点。引擎万一炸了也不能发出错形状。

    MxToken 也必须给够 64 字符：有会话就用会话的，没有就由账号派生（sha384->base64）。
    兜底路径同样要过 report/102 §3 的 7 项 —— 形状错误比数值错误更致命。
    """
    import base64 as _b64
    import hashlib as _h
    import uuid as _uuid
    try:
        aid = int(getattr(SESSION, 'account_id', 0) or 0)
    except Exception:
        aid = 0
    sk = _ba24000_session_key()
    tok = str(sk.get('MxToken')) if (sk and sk.get('MxToken')) else ''
    if not tok:
        tok = _b64.b64encode(_h.sha384(('ba24000:%d' % aid).encode('utf-8')).digest()).decode('ascii')
    try:
        ticks = _ba24000_now_ticks()
    except Exception:
        ticks = 0
    try:
        lu = b24000_fmt_time(b24000_time_from_ticks(ticks))
    except Exception:
        lu = '0001-01-01T00:00:00'
    rid = str(_uuid.uuid4())
    rec['academy_account_id'] = aid
    rec['academy_ticks'] = ticks
    rec['academy_request_id'] = rid
    rec['academy_last_update'] = lu
    rec['academy_top_keys'] = list(B24000_TOP_KEYS)
    rec['academy_zv_keys'] = len(B24000_ZONE_KEY_ORDER)
    rec['academy_zv_is_dict'] = True
    rec['academy_locations'] = 1
    rec['academy_token_len'] = len(tok)
    rec['academy_token_is64'] = (len(tok) == 64)
    rec['academy_token_src'] = 'session' if (sk and sk.get('MxToken')) else 'generated'
    rec['academy_schedule_empty'] = True
    rec['academy_no_pseudo_keys'] = True
    return {
        'Protocol': B24000_PROTO,
        'SessionKey': {'AccountServerId': aid, 'MxToken': tok},
        'ServerTimeTicks': ticks,
        'ServerNotification': 0,
        'RequestId': rid,
        'AcademyDB': {
            'AccountId': aid,
            'LastUpdate': lu,
            'ZoneVisitCharacterDBs': dict((k, []) for k in B24000_ZONE_KEY_ORDER),
            'ZoneScheduleGroupRecords': {},
        },
        'AcademyLocationDBs': [{'AccountId': aid, 'LocationId': 1, 'Rank': 1, 'Exp': 0}],
    }


def _ba24000_send(proto_name, obj, rec):
    """和 _cn_send_envelope 一样的容器，但**外层 requestid == 内层 RequestId**（官方行为）。

    _cn_send_envelope 是自己新生成一个 rid 传给 wrap_response，且不回填 inner.RequestId，
    所以客户端拿到的 RequestId 与 HTTP 头对不上 —— 这就是"下一条请求没有来源"的直接原因。
    """
    import json as _json
    import uuid as _uuid
    rid = obj.get('RequestId') or str(_uuid.uuid4())
    obj['RequestId'] = rid
    inner = b24000_compact(obj)
    wire, plain, _key = cn_wire.wrap_response(proto_name, obj, rid)
    rec['wrap_mode'] = 'direct_envelope'
    rec['enc_requestid'] = rid
    rec['enc_inner_keys'] = len(obj)
    rec['enc_inner_bytes'] = len(inner.encode('utf-8'))
    rec['enc_plain_len'] = len(plain)
    rec['enc_body_len'] = len(wire)
    try:
        _p = _json.loads(plain)
        rec['academy_rid_match'] = (_p.get('requestid') == rid)
        rec['academy_rid_inner_match'] = (
            _json.loads(_p.get('packet') or '{}').get('RequestId') == rid)
    except Exception as e:
        rec['academy_rid_match'] = False
        rec['academy_rid_inner_match'] = False
        rec['academy_rid_parse_err'] = repr(e)
    rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
    try:
        open('/www/wwwroot/_ba_state/last_direct_envelope_plain.txt', 'w').write(plain)
    except Exception:
        pass
    return 200, wire, 'text/plain; charset=utf-8'
'''


# ================================================================ 基础工具
def die(msg, code=2):
    sys.stderr.write('ERROR: %s\n' % msg)
    raise SystemExit(code)


def read_text(path):
    with open(path, 'rb') as fh:
        return fh.read().decode('utf-8')


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def write_text_atomic(path, text):
    tmp = path + '.tmp_24000v3'
    with open(tmp, 'wb') as fh:
        fh.write(text.encode('utf-8'))
    if os.path.exists(path):
        shutil.copymode(path, tmp)
    os.replace(tmp, path)


def stamp():
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def unique_backup_path(target, ts):
    bak = target + '.bak.' + ts
    n = 1
    while os.path.exists(bak):
        bak = target + '.bak.' + ts + '_%d' % n
        n += 1
    return bak


def eol_cr(text):
    crlf = text.count('\r\n')
    return '\r' if crlf > (text.count('\n') - crlf) else ''


def count_lines(text):
    """行数口径与 wc -l 一致（结尾换行不算一行）。"""
    n = text.count('\n')
    if text and not text.endswith('\n'):
        n += 1
    return n


def under(path, directory):
    p = os.path.abspath(path)
    d = os.path.abspath(directory)
    return p == d or p.startswith(d + os.sep)


# ================================================================ 目标定位 / 守卫
def resolve_target(explicit):
    """定位 bridge：显式 --target 优先；否则只认线上候选路径。

    **绝不自动指向 _baseline** —— 基线是只读的。
    """
    cands = []
    if explicit:
        cands.append(explicit)
    cands.extend(TARGET_CANDIDATES)
    for path in cands:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            continue
        try:
            if 'if num == 24000:' in read_text(path):
                return path
        except Exception:
            continue
    die('找不到含 "if num == 24000:" 的 account_auth_probe.py\n'
        '  本地演练请显式给 --target（先复制基线到临时目录）：\n'
        '    copy %s %%TEMP%%\\aap.py\n'
        '    python patch_24000_v3.py --target %%TEMP%%\\aap.py --dry-run' % BASELINE_FILE)


def guard_write(path):
    """拒绝写入基线 / 旧快照目录。只读操作（--dry-run/--verify）不走这里。"""
    if under(path, BASELINE_DIR):
        die('拒绝写入基线目录（只读）：%s\n'
            '  正确做法：复制到临时目录再打补丁\n'
            '    copy "%s" %%TEMP%%\\aap.py' % (os.path.abspath(path), BASELINE_FILE))
    if under(path, BRIDGE_REF_DIR):
        die('拒绝写入旧快照目录 _bridge_ref（就是 v2 用错的那份）：%s' % os.path.abspath(path))


def baseline_gate(a, text, sha):
    """--apply 的目标必须是已知基线，或已含 v3 托管块（幂等重跑）。"""
    if BLOCK_BEGIN in text:
        return 'already-v3'
    if sha == BASELINE_SHA256:
        return 'baseline'
    for marker, who in ((BEGIN_V2, 'v2'), (BEGIN_292, '292')):
        if marker in text:
            die('目标已是 %s 补丁态（含 %r）。请先 --rollback 回基线再打 v3，'
                '否则两套同名托管符号会互相覆盖。' % (who, marker))
    if a.allow_other_baseline:
        return 'other(forced)'
    die('目标 sha256 不是已知基线，拒绝改动：\n'
        '  got      %s\n  expect   %s\n'
        '  （--allow-other-baseline 可越过；基线文件 = %s）'
        % (sha, BASELINE_SHA256, BASELINE_FILE))


# ================================================================ 引擎
def load_engine(path_arg):
    """定位并导入 gen24000.py（引擎唯一真源；不重写、不改动）。"""
    cands = []
    if path_arg:
        cands.append(path_arg)
    cands.extend((os.path.join(HERE, ENGINE_FILE_NAME),
                  os.path.join(os.getcwd(), ENGINE_FILE_NAME),
                  '/www/wwwroot/bapatch/' + ENGINE_FILE_NAME))
    for path in cands:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            continue
        spec = importlib.util.spec_from_file_location('_ba24000_engine', path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            die('导入引擎失败 %s: %r' % (path, e))
        return path, mod
    die('找不到 %s（必须与补丁脚本同一目录）；--engine 可显式指定' % ENGINE_FILE_NAME)


# ================================================================ 文本结构操作
def find_branch(lines):
    """-> (start, end, indent)：整段 `if num == 24000:` 分支（0-based，end 不含）。"""
    pat = re.compile(r'^(\s*)if num == 24000:\s*$')
    for i, raw in enumerate(lines):
        s = raw.rstrip('\r')
        m = pat.match(s)
        if not m:
            continue
        indent = m.group(1)
        j = i + 1
        while j < len(lines):
            cand = lines[j].rstrip('\r')
            if cand.strip() == '':
                j += 1
                continue
            if len(cand) - len(cand.lstrip()) <= len(indent):
                break
            j += 1
        end = j
        while end > i + 1 and lines[end - 1].strip() == '':
            end -= 1
        return i, end, indent
    die('"if num == 24000:" 分支不存在 —— 目标不是预期的文件')


def find_marker(lines, begin, end):
    """-> (begin_idx, end_idx) 或 (None, None)。有 BEGIN 无 END 直接拒绝动手。"""
    bi = ei = None
    for i, raw in enumerate(lines):
        s = raw.rstrip('\r')
        if s == begin and bi is None:
            bi = i
        elif s == end and bi is not None and ei is None:
            ei = i
            break
    if bi is not None and ei is None:
        die('托管块 BEGIN 没有配对的 END —— 拒绝改动文件')
    return bi, ei


def find_anchor(lines):
    """托管块插入锚点：`SESSION = Session()` 之后（宿主定义会话单例处，基线 L508）。

    这里必须有**唯一**命中且不在任何缩进块里，否则落到 `class` 前 / 最后一个 import 后。
    """
    hits = [i for i, raw in enumerate(lines) if raw.rstrip('\r') == 'SESSION = Session()']
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        die('宿主里 `SESSION = Session()` 出现 %d 次，无法确定插入锚点' % len(hits))
    for i, raw in enumerate(lines):
        if re.match(r'^class\s+\w+', raw.rstrip('\r')):
            die('宿主里没有 `SESSION = Session()`；请人工确认插入锚点（最近 class %s 在 L%d）'
                % (raw.strip(), i + 1))
    last = None
    for i, raw in enumerate(lines):
        s = raw.rstrip('\r')
        if s.startswith('import ') or s.startswith('from '):
            last = i
    return last if last is not None else 0


def replace_branch(lines, cr):
    start, end, indent = find_branch(lines)
    old = list(lines[start:end])
    new = [indent + b + cr for b in BRANCH_NEW]
    return lines[:start] + new + lines[end:], {'old_n': len(old), 'new_n': len(new)}


def put_block(lines, block_lines, cr):
    """托管块：已存在就整段替换，不存在就插到锚点后（幂等靠整段逐行比对）。"""
    block = [l + cr for l in block_lines]
    bi, ei = find_marker(lines, BLOCK_BEGIN, BLOCK_END)
    if bi is not None:
        if lines[bi:ei + 1] == block:
            return lines, 'unchanged'
        return lines[:bi] + block + lines[ei + 1:], 'replaced'
    anchor = find_anchor(lines)
    tail = [cr] if (anchor + 1 >= len(lines) or lines[anchor + 1].strip() != '') else []
    return lines[:anchor + 1] + [cr] + block + tail + lines[anchor + 1:], 'inserted'


def build_block_lines(engine):
    """托管块全文（**不含时间戳**，否则幂等就废了）。"""
    header = [
        '# ' + '=' * 74,
        '# 24000_v3 managed block -- DO NOT EDIT BY HAND',
        '# 由 work/ba/server/deploy/patch_24000_v3.py 生成',
        '# 基线 = _baseline/account_auth_probe.py  %d B  sha256 %s' % (BASELINE_BYTES,
                                                                    BASELINE_SHA256),
        '# 24000_v3 meta: engine=%s sha256=%s' % (engine.ENGINE_VERSION, engine.engine_sha256()),
        '# 结构权威 = work/ba/proto/official_spec.json protocols["24000"]'
        '（7 键 / 71 zone / ZoneScheduleGroupRecords={} / RequestId==外层 requestid）',
        '# 撤销：python3 patch_24000_v3.py --target <file> --rollback',
        '# ' + '=' * 74,
    ]
    out = [BLOCK_BEGIN]
    out += header
    out += engine.engine_source().split('\n')
    out += ADAPTER_SRC.strip('\n').split('\n')
    out += [BLOCK_END]
    return out


def compose(engine, text):
    """-> (new_text, notes, info)。先插块（在上），再换分支（在下），最后重算真实行号。"""
    cr = eol_cr(text)
    lines = text.split('\n')
    notes = []

    block_lines = build_block_lines(engine)
    lines, blk_state = put_block(lines, block_lines, cr)
    notes.append({'inserted': '托管块插入 %d 行', 'replaced': '托管块整段替换 %d 行',
                  'unchanged': '托管块已是目标内容 %d 行（无变化）'}[blk_state]
                 % len(block_lines))

    lines, br = replace_branch(lines, cr)
    if br['old_n'] == br['new_n']:
        notes.append('24000 分支已是 v3（%d 行，无变化）' % br['new_n'])
    else:
        notes.append('24000 分支 %d 行 -> %d 行' % (br['old_n'], br['new_n']))

    new = '\n'.join(lines)
    start, end, indent = find_branch(lines)
    bi, ei = find_marker(lines, BLOCK_BEGIN, BLOCK_END)
    info = {'branch': (start + 1, end), 'branch_indent': len(indent),
            'block': (bi + 1, ei + 1), 'blk_state': blk_state,
            'old_n': br['old_n'], 'new_n': br['new_n'], 'lines': count_lines(new)}
    return new, notes, info


# ================================================================ 执行沙箱
class StubSession(object):
    account_id = None
    session_key = None


class StubCnWire(object):
    """镜像 cn_wire.wrap_response 的明文构造：{"protocol","packet","requestid"}。

    本机没有 cryptography 时用它（cn_wire.py 顶层 import cryptography）。
    rid 链的断言只依赖明文构造，与 AES 无关。
    """

    @staticmethod
    def wrap_response(proto_name, inner_obj, requestid=None, key=None):
        plain = json.dumps({'protocol': proto_name,
                            'packet': json.dumps(inner_obj, ensure_ascii=False,
                                                 separators=(',', ':')),
                            'requestid': requestid},
                           ensure_ascii=False, separators=(',', ':'))
        return b'STUB-WIRE-BODY', plain, b'0' * 32


def load_cn_wire(target):
    """优先用目标目录里的真实 cn_wire（wraps AES），没有就退回 StubCnWire。"""
    path = os.path.join(os.path.dirname(os.path.abspath(target)), 'cn_wire.py')
    if os.path.exists(path):
        try:
            spec = importlib.util.spec_from_file_location('_ba_cn_wire', path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod, path
        except Exception:
            pass
    return StubCnWire, None


def extract_block(text):
    lines = text.split('\n')
    bi, ei = find_marker(lines, BLOCK_BEGIN, BLOCK_END)
    if bi is None:
        die('托管块不存在 —— 先 --apply（或目标没被本补丁改过）')
    return '\n'.join(lines[bi:ei + 1]), bi, ei


def exec_block(block_text, cn_wire_mod):
    ns = {'__name__': 'ba24000_block', 'SESSION': StubSession(), 'cn_wire': cn_wire_mod}
    exec(compile(block_text, '<24000_v3_block>', 'exec'), ns)
    return ns


def fake_fragment(account_id, mxtoken):
    return ('{"Protocol":24000,"Hash":103079215104002,"IsTest":false,'
            '"SessionKey":{"AccountServerId":%d,"MxToken":"%s"},'
            '"AccountId":%d,"OSType":2}' % (account_id, mxtoken, account_id))


def guess_real_account(target):
    """从 bridge 日志尾部捡最近一个真实账号 + MxToken。取不到返回 None。"""
    cands = ['/www/wwwroot/bapatch/logs/api_all_requests.log',
             '/www/wwwroot/bapatch/logs/all_paths.log',
             os.path.join(os.path.dirname(os.path.abspath(target)),
                          'logs', 'api_all_requests.log'),
             os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(target))),
                          'logs', 'api_all_requests.log')]
    for path in cands:
        if not os.path.exists(path):
            continue
        try:
            size = os.path.getsize(path)
            with open(path, 'rb') as fh:
                fh.seek(max(0, size - 512 * 1024))
                tail = fh.read().decode('utf-8', 'replace')
        except Exception:
            continue
        aids = re.findall(r'"AccountServerId"\s*:\s*(\d+)', tail) \
            or re.findall(r'"AccountId"\s*:\s*(\d+)', tail)
        toks = re.findall(r'"MxToken"\s*:\s*"([A-Za-z0-9+/=_-]{16,})"', tail)
        if aids:
            return int(aids[-1]), (toks[-1] if toks else None), path
    return None


# ================================================================ 7 项结构核对
def seven_fixes(obj, outer_rid=None):
    """对照 report/102 §3 逐项判定 -> [{'n','name','ok','detail'}]。不抛异常。"""
    out = []

    def add(n, name, ok, detail=''):
        out.append({'n': n, 'name': name, 'ok': bool(ok), 'detail': str(detail)})

    obj = obj if isinstance(obj, dict) else {}
    adb = obj.get('AcademyDB') if isinstance(obj.get('AcademyDB'), dict) else {}
    zv = adb.get('ZoneVisitCharacterDBs')
    locs = obj.get('AcademyLocationDBs')
    sk = obj.get('SessionKey') if isinstance(obj.get('SessionKey'), dict) else {}
    rid = obj.get('RequestId')

    # ① ZoneVisitCharacterDBs 是 dict（71 个 zone key），值都是数组
    nzk = len(zv) if hasattr(zv, '__len__') else -1
    ok1 = (isinstance(zv, dict) and nzk == 71
           and all(isinstance(v, list) for v in zv.values()))
    add(1, 'ZoneVisitCharacterDBs 是 dict（71 个 zone key）', ok1,
        '%s / %d keys / 值全数组=%s' % (type(zv).__name__, nzk,
                                        isinstance(zv, dict)
                                        and all(isinstance(v, list) for v in zv.values())))
    # ② AcademyDB.AccountId
    add(2, 'AcademyDB.AccountId 是 int', isinstance(adb.get('AccountId'), int),
        repr(adb.get('AccountId')))
    # ③ AcademyLocationDBs 每条都有 AccountId（且 4 键齐全）
    if isinstance(locs, list) and locs:
        bad = [i for i, r in enumerate(locs)
               if not isinstance(r, dict) or not isinstance(r.get('AccountId'), int)
               or tuple(r.keys()) != ('AccountId', 'LocationId', 'Rank', 'Exp')]
        add(3, 'AcademyLocationDBs 每条有 AccountId（4 键）', not bad,
            '%d 条, 不合格行=%r' % (len(locs), bad[:5]))
    else:
        add(3, 'AcademyLocationDBs 每条有 AccountId（4 键）', False,
            'AcademyLocationDBs 不是非空数组: %r' % (type(locs).__name__,))
    # ④ ZoneScheduleGroupRecords == {}
    add(4, 'ZoneScheduleGroupRecords == {}', adb.get('ZoneScheduleGroupRecords') == {},
        '%s / %d keys' % (type(adb.get('ZoneScheduleGroupRecords')).__name__,
                          len(adb.get('ZoneScheduleGroupRecords'))
                          if hasattr(adb.get('ZoneScheduleGroupRecords'), '__len__') else -1))
    # ⑤ SessionKey{AccountServerId, MxToken(64 字符 base64)}
    tok = sk.get('MxToken')
    ok5 = (tuple(sk.keys()) == ('AccountServerId', 'MxToken')
           and isinstance(sk.get('AccountServerId'), int)
           and isinstance(tok, str) and len(tok) == 64
           and re.match(r'^[A-Za-z0-9+/=]+$', tok or '') is not None)
    add(5, 'SessionKey {AccountServerId, MxToken(64 字符 base64)}', ok5,
        'keys=%r token_len=%d' % (list(sk.keys()) if sk else [], len(tok) if isinstance(tok, str) else -1))
    # ⑥ RequestId（值 = 外层 requestid）
    ok6 = isinstance(rid, str) and len(rid) >= 8
    det6 = '%r' % (rid,)
    if outer_rid is not None:
        ok6 = ok6 and (rid == outer_rid)
        det6 += ' 外层=%r 同值=%s' % (outer_rid, rid == outer_rid)
    add(6, 'RequestId 存在（值 = 外层 requestid）', ok6, det6)
    # ⑦ 无 4 个伪键
    found = [k for k in PSEUDO_KEYS if k in obj]
    add(7, '无 MissionProgressDBs/EventMissionProgressDBDict/'
           'BattlePassMissionProgressDBDict/StaticOpenConditions', not found,
        '多出=%r' % (found,))
    return out


def print_seven(fixes, prefix='    '):
    for f in fixes:
        print('%s%s %d) %s  [%s]' % (prefix, 'PASS' if f['ok'] else 'FAIL',
                                     f['n'], f['name'], f['detail']))


# ================================================================ 4 道闸
def gate1_compile(text, target):
    try:
        compile(text, target, 'exec')
    except SyntaxError as e:
        die('[闸1 compile] 改后文件语法错误，未写入：%s' % e)
    print('  闸 1 compile          : PASS')


def gate2_names(engine, host_text):
    """托管块要新增的顶层名字，不能与宿主现有顶层名字撞。"""
    import ast
    new_names = []
    for src in (engine.engine_source(), ADAPTER_SRC):
        for node in ast.parse(src).body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                new_names.append(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        new_names.append(t.id)
    host = set()
    lines = host_text.split('\n')
    bi, ei = find_marker(lines, BLOCK_BEGIN, BLOCK_END)
    keep = [l for i, l in enumerate(lines) if not (bi is not None and bi <= i <= ei)]
    for node in ast.parse('\n'.join(keep)).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            host.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    host.add(t.id)
    clash = sorted(set(new_names) & host)
    if clash:
        die('[闸2 撞名] 宿主已有同名顶层符号，拒绝插入（会覆盖）：%r' % clash)
    print('  闸 2 顶层撞名         : PASS（新增 %d 个 b24000_*/_ba24000_* 名字，宿主 %d 个，无交集）'
          % (len(set(new_names)), len(host)))


def gate3_engine(engine, ns):
    """引擎核同输入同字节 + 引擎 vs 官方抓包逐字节。"""
    ref = engine.b24000_build(**FIXED_CASE)
    got = ns['b24000_build'](**FIXED_CASE)
    same_obj = (ref == got)
    ref_bytes = engine.b24000_compact(ref).encode('utf-8')
    got_bytes = ns['b24000_compact'](got).encode('utf-8')
    same_bytes = ref_bytes == got_bytes
    if not (same_obj and same_bytes):
        die('[闸3 引擎核] 托管块内联核与 gen24000.py 不一致（dict 同=%s 字节同=%s）'
            % (same_obj, same_bytes))
    print('  闸 3 引擎核同字节     : PASS（同 dict / 同紧凑字节 %d B / engine sha256 %s）'
          % (len(got_bytes), engine.engine_sha256()[:16]))
    fid = None
    try:
        fid = engine.fidelity_check(verbose=False)
    except Exception as e:
        print('  闸 3+ 官方逐字节      : SKIP（%r）' % (e,))
        return
    if fid is None:
        print('  闸 3+ 官方逐字节      : SKIP（抓包 fixture 不存在）')
    elif fid:
        print('  闸 3+ 官方逐字节      : PASS（%d B 逐字节相同）'
              % EXPECTED_INNER_BYTES_OFFICIAL)
    else:
        die('[闸3 引擎核] 引擎渲染与官方 packet 不是逐字节相同（引擎被改过？）')


def gate4_chains(engine, ns):
    """build / send / 兜底 三链自测 + 7 项结构。"""
    aid, tok = FIXED_CASE['account_id'], FIXED_CASE['mxtoken']

    # 链 1：build
    rec1, rec2 = {}, {}
    o1 = ns['_ba24000_build'](fake_fragment(aid, tok), rec1)
    o2 = ns['_ba24000_build'](fake_fragment(aid, tok), rec2)
    c1 = ns['b24000_check'](o1)
    c2 = ns['b24000_check'](o2)
    fresh = (o1.get('RequestId') != o2.get('RequestId'))
    if not (c1['ok'] and c2['ok'] and fresh):
        print_seven(seven_fixes(o1))
        die('[闸4 链1 build] 结构不合法或 RequestId 没有每条新生成（ok=%s/%s fresh=%s）%r'
            % (c1['ok'], c2['ok'], fresh, c1['problems']))

    # 链 2：send（外层 requestid == 内层 RequestId）
    rec3 = {}
    code, body, ctype = ns['_ba24000_send']('Academy_GetInfo', dict(o1), rec3)
    ok_send = (code == 200 and bool(body) and bool(rec3.get('academy_rid_match'))
               and bool(rec3.get('academy_rid_inner_match')))
    if not ok_send:
        die('[闸4 链2 send] 外层 requestid != 内层 RequestId 或发送失败：%r'
            % ({k: rec3.get(k) for k in ('academy_rid_match', 'academy_rid_inner_match',
                                         'academy_rid_parse_err', 'enc_requestid')},))

    # 链 3：兜底
    mk = ns['_ba24000_minimal']({})
    mk_chk = ns['b24000_check'](mk)
    if not mk_chk['ok']:
        print_seven(seven_fixes(mk))
        die('[闸4 链3 兜底] 兜底结构不合法：%r' % (mk_chk['problems'],))

    fix1 = seven_fixes(o1, outer_rid=rec3.get('enc_requestid'))
    fix3 = seven_fixes(mk)
    bad = [f for f in fix1 + fix3 if not f['ok']]
    if bad:
        print_seven(fix1)
        die('[闸4 链1] 7 项结构核对未全过：%r' % ([f['n'] for f in bad],))

    print('  闸 4 build+send+兜底  : PASS')
    print('       链1 build      : 7 键 / %d zone / %d 地点 / inner %d B / RequestId 每条新生成'
          % (c1['zone_keys'], c1['locations'], c1['inner_bytes']))
    print('       链2 send       : 200 %s / 外层rid==内层rid / 内层packet里的 RequestId 也同值'
          % ctype.split(';')[0])
    print('       链3 兜底       : 7 键 / 71 zone / 1 地点（引擎异常时也不会发出错形状）')
    print('       7 项结构        : 全部 PASS')
    print_seven(fix1)
    return {'build_keys': c1['top_keys'], 'zone': c1['zone_keys'],
            'locations': c1['locations'], 'inner_bytes': c1['inner_bytes'],
            'rid': o1.get('RequestId'), 'seven': fix1}


# ================================================================ manifest
def manifest_path(a, target):
    """manifest 落在已存在且可写的目录里；**不创建任何新目录**。"""
    if a.manifest:
        return a.manifest
    tdir = os.path.dirname(os.path.abspath(target))
    name = 'patch_24000_v3_manifest.%s.json' % os.path.basename(os.path.abspath(target))
    for d in list(DEFAULT_MANIFEST_DIRS) + [tdir]:
        if not d or not os.path.isdir(d):
            continue
        try:
            probe = os.path.join(d, '.patch24000v3.writable')
            with open(probe, 'w') as fh:
                fh.write('ok')
            os.remove(probe)
            return os.path.join(d, name)
        except Exception:
            continue
    return os.path.join(tdir, name)


def load_manifest(a, target):
    """target 字段对不上的（别的目标的）一律忽略。"""
    tgt = os.path.abspath(target)
    for p in (a.manifest, manifest_path(a, target)):
        if p and os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                if not isinstance(data, dict):
                    continue
                mt = data.get('target')
                if mt and os.path.abspath(mt) != tgt:
                    continue
                return data, p
            except Exception:
                continue
    return None, None


# ================================================================ 命令
def cmd_apply(a, engine, target):
    old = read_text(target)
    orig_sha = sha256_text(old)
    orig_bytes = len(old.encode('utf-8'))
    orig_lines = count_lines(old)

    state = baseline_gate(a, old, orig_sha)

    print('=' * 78)
    print('24000 v3 · apply   %s' % target)
    print('=' * 78)
    print('target           : %s' % target)
    print('原始文件         : %d B / %d 行 / sha256=%s' % (orig_bytes, orig_lines, orig_sha))
    print('基线身份         : %s' % {
        'baseline': '已知基线（%d B / sha256 %s…）' % (BASELINE_BYTES, BASELINE_SHA256[:16]),
        'already-v3': '已含 v3 托管块（幂等重跑）',
        'other(forced)': '** 非已知基线，--allow-other-baseline 越过 **',
    }[state])
    print('engine           : %s  v%s  sha256=%s'
          % (a.engine_path, engine.ENGINE_VERSION, engine.engine_sha256()[:16]))

    # 基线形状核对（只在目标就是已知基线时严格校验）
    pb_start, pb_end, pb_n = BASELINE_BRANCH
    b_start, b_end, b_indent = find_branch(old.split('\n'))
    got_branch = (b_start + 1, b_end, b_end - b_start)
    print('24000 分支定位   : L%d-%d（%d 行），缩进 %d'
          % (got_branch[0], got_branch[1], got_branch[2], len(b_indent)))
    if state == 'baseline':
        if got_branch != (pb_start, pb_end, pb_n):
            die('基线的 24000 分支位置与记录不符：got L%d-%d (%d 行) / expect L%d-%d (%d 行)'
                % (got_branch + (pb_start, pb_end, pb_n)))
        if orig_lines != BASELINE_LINES:
            die('基线行数与记录不符：got %d / expect %d' % (orig_lines, BASELINE_LINES))
        e2 = any(BASELINE_E2_MARK in l for l in old.split('\n')[b_start:b_end])
        if not e2:
            die('基线的 24000 分支里没有 %r —— 不是 E2 版基线' % BASELINE_E2_MARK)
        print('基线形状         : PASS（E2 版签名 %r 命中；%d 行 == 记录的 %d 行）'
              % (BASELINE_E2_MARK, got_branch[2], pb_n))

    new, notes, info = compose(engine, old)
    for n in notes:
        print('note             : %s' % n)

    # ---- 4 道闸（无论是否需要写入都跑，第二遍 apply 也要能证明全绿）----
    print()
    print('--- 写入前 4 道闸 ---')
    gate1_compile(new, target)
    gate2_names(engine, old)
    block_text, bi, ei = extract_block(new)
    cn_wire_mod, cn_wire_path = load_cn_wire(target)
    print('  cn_wire               : %s' % (cn_wire_path
                                             or 'StubCnWire（本机无 cryptography；只验 rid 链）'))
    ns = exec_block(block_text, cn_wire_mod)
    gate3_engine(engine, ns)
    gate4_chains(engine, ns)

    print()
    print('--- 改动摘要 ---')
    print('分支             : L%d-%d  %d 行 -> %d 行'
          % (b_start + 1, b_end, info['old_n'], info['new_n']))
    print('新分支位置       : L%d-%d（插块后重算）' % info['branch'])
    print('托管块           : L%d-%d（%d 行，状态=%s）'
          % (info['block'][0], info['block'][1], ei - bi + 1, info['blk_state']))
    print('改后文件         : %d 行 / %d B（%+d B）'
          % (info['lines'], len(new.encode('utf-8')),
             len(new.encode('utf-8')) - orig_bytes))

    if new == old:
        print()
        print('结果             : 已是最新，无需改动（幂等）；sha256 不变 = %s' % orig_sha)
        print('APPLY: PASS (no-op)')
        return 0

    ts = stamp()
    bak = unique_backup_path(target, ts)
    if a.dry_run:
        print()
        print('[dry-run] 会备份     : %s' % bak)
        print('[dry-run] 会写入     : %s' % target)
        print('[dry-run] 没有写入任何文件')
        return 0

    shutil.copy2(target, bak)
    try:
        write_text_atomic(target, new)
        compile(read_text(target), target, 'exec')
    except Exception:
        shutil.copy2(bak, target)
        die('写入/复检失败，已从 %s 还原\n%s' % (bak, traceback.format_exc()))

    manifest = {
        'patch': PATCH_NAME,
        'engine_version': engine.ENGINE_VERSION,
        'engine_sha256': engine.engine_sha256(),
        'baseline_sha256': BASELINE_SHA256,
        'baseline_bytes': BASELINE_BYTES,
        'target': os.path.abspath(target),
        'applied_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'original_sha256': orig_sha,
        'original_bytes': orig_bytes,
        'original_lines': orig_lines,
        'patched_sha256': sha256_text(read_text(target)),
        'patched_bytes': os.path.getsize(target),
        'backup': bak,
        'branch_old': [b_start + 1, b_end],
        'branch_new': list(info['branch']),
        'block_lines': list(info['block']),
    }
    mpath = manifest_path(a, target)
    try:
        with open(mpath, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=1)
            fh.write('\n')
        print()
        print('manifest         : %s' % mpath)
    except Exception as e:
        print('manifest         : 写失败（不影响 --rollback）: %r' % (e,))

    print()
    print('patched          : %s (%d B, %+d)' % (target, manifest['patched_bytes'],
                                                manifest['patched_bytes'] - orig_bytes))
    print('backup           : %s  sha256=%s' % (bak, sha256_file(bak)))
    print('compile 复检     : OK')
    print('原 sha256        : %s' % orig_sha)
    print('新 sha256        : %s' % manifest['patched_sha256'])
    print('回滚             : python3 %s --target %s --rollback'
          % (os.path.abspath(__file__), target))
    print('核对             : python3 %s --target %s --verify'
          % (os.path.abspath(__file__), target))
    print('APPLY: PASS')
    return 0


def cmd_verify(a, engine, target):
    text = read_text(target)
    lines = text.split('\n')
    start, end, indent = find_branch(lines)
    sha = sha256_file(target)

    print('=' * 78)
    print('24000 v3 · verify  %s' % target)
    print('=' * 78)
    print('文件             : %d B / %d 行 / sha256=%s / EOL=%s'
          % (os.path.getsize(target), count_lines(text), sha,
             'CRLF' if eol_cr(text) else 'LF'))
    print('补丁状态         : %s' % ('已应用 v3' if BLOCK_BEGIN in text else '** 未应用 **'))
    print('与基线 sha256    : %s' % ('相同（这就是基线本身）' if sha == BASELINE_SHA256
                                     else '不同（已打补丁或另有改动）'))
    print()
    print('--- 当前 24000 分支（L%d-%d，%d 行）---' % (start + 1, end, end - start))
    for n, raw in enumerate(lines[start:end], start + 1):
        print('%5d | %s' % (n, raw.rstrip('\r')))
    tail = lines[end].rstrip('\r') if end < len(lines) else ''
    print('%5d | %s   <- 分支后的下一行（必须是同级 dedent）' % (end + 1, tail))

    if BLOCK_BEGIN not in text:
        print()
        print('VERIFY: FAIL（托管块不存在，先跑 --apply）')
        return 1

    body = [l.rstrip('\r')[len(indent):] for l in lines[start:end]]
    shape_ok = (body == BRANCH_NEW)
    e2_gone = not any((BASELINE_E2_MARK in l) or ('ZoneScheduleGroupRecords' in l)
                      for l in lines[start:end])
    print()
    print('分支形状         : %s（== 6 行 v3 模板；%d 行）'
          % ('PASS' if shape_ok else 'FAIL', end - start))
    print('E2 旧结构已清除  : %s（分支里再无 %r / ZoneScheduleGroupRecords）'
          % ('PASS' if e2_gone else 'FAIL', BASELINE_E2_MARK))

    block_text, bi, ei = extract_block(text)
    print()
    print('--- 托管块（L%d-%d，%d 行）---' % (bi + 1, ei + 1, ei - bi + 1))
    print('引擎核标记       : %s' % ('OK' if 'ENGINE CORE (24000 v2)' in block_text else '缺失'))
    m = re.search(r'24000_v3 meta: engine=([0-9.]+) sha256=([0-9a-f]{64})', block_text)
    same_engine = False
    if m:
        print('块内引擎         : v%s sha256=%s' % (m.group(1), m.group(2)[:16]))
        same_engine = (m.group(2) == engine.engine_sha256())
        print('与 gen24000.py   : %s' % ('一致'
                                        if same_engine
                                        else '** 不一致（引擎已升级或块被手改，需重新 --apply）**'))
    else:
        print('块内引擎         : 读不到 meta 行')

    cn_wire_mod, cn_wire_path = load_cn_wire(target)
    ns = exec_block(block_text, cn_wire_mod)
    print('cn_wire          : %s' % (cn_wire_path or 'StubCnWire'))
    print()
    print('--- 引擎核一致性 ---')
    try:
        gate3_engine(engine, ns)
        par = True
    except SystemExit:
        par = False

    print()
    print('--- 用真实账号数据渲染一次 ---')
    real = None
    if a.account_id:
        real = (int(a.account_id), a.mxtoken, '命令行 --account-id')
    else:
        real = guess_real_account(target)
    if real:
        aid, tok, src = real
        print('账号来源         : %s' % src)
    else:
        aid, tok = FIXED_CASE['account_id'], FIXED_CASE['mxtoken']
        print('账号来源         : 抓包样本（日志里找不到真实账号）')
    if not tok:
        tok = engine.derive_token(aid)
        print('MxToken          : 由账号派生（日志里没有 MxToken）')
    rec = {}
    obj = ns['_ba24000_build'](fake_fragment(aid, tok), rec)
    chk = ns['b24000_check'](obj)
    inner = ns['b24000_compact'](obj)
    rec3 = {}
    code, _body, _ctype = ns['_ba24000_send']('Academy_GetInfo', dict(obj), rec3)
    print('AccountServerId  : %d  (%s)' % (obj['SessionKey']['AccountServerId'],
                                           rec.get('academy_account_src')))
    print('MxToken          : %d 字符 (is64=%s, src=%s)'
          % (rec.get('academy_token_len', 0), rec.get('academy_token_is64'),
             rec.get('academy_token_src')))
    print('RequestId        : %s  (src=%s)' % (obj['RequestId'], rec.get('academy_rid_src')))
    print('ServerTimeTicks  : %d' % obj['ServerTimeTicks'])
    print('LastUpdate       : %s' % obj['AcademyDB']['LastUpdate'])
    print('顶层键           : %d %r' % (len(chk['top_keys']), chk['top_keys']))
    print('inner JSON 字节  : %d' % len(inner.encode('utf-8')))
    print('ZoneVisitCharacterDBs: %d 键 (dict=%s)'
          % (chk['zone_keys'], isinstance(obj['AcademyDB']['ZoneVisitCharacterDBs'], dict)))
    print('AcademyLocationDBs   : %d 条 %r'
          % (chk['locations'], [(r['LocationId'], r['Rank'], r['Exp'])
                                for r in obj['AcademyLocationDBs']]))
    print('结构自检         : %s %s' % ('PASS' if chk['ok'] else 'FAIL', chk['problems']))
    print('外层rid==内层rid : %s' % ('PASS' if rec3.get('academy_rid_match') else 'FAIL'))
    print()
    print('--- 7 项结构核对（report/102 §3）---')
    fix = seven_fixes(obj, outer_rid=rec3.get('enc_requestid'))
    print_seven(fix, prefix='  ')
    print()
    print('官方 inner 参考  : %d B（9 条地点 + 276 条 zone 记录；新号数据更少所以更小）'
          % EXPECTED_INNER_BYTES_OFFICIAL)
    good = (shape_ok and e2_gone and par and same_engine and chk['ok']
            and bool(rec3.get('academy_rid_match')) and all(f['ok'] for f in fix))
    print()
    print('VERIFY: %s' % ('PASS' if good else 'FAIL'))
    return 0 if good else 1


def cmd_rollback(a, target):
    manifest, mpath = load_manifest(a, target)
    d = os.path.dirname(os.path.abspath(target))
    base = os.path.basename(target)
    cands = sorted(n for n in os.listdir(d) if n.startswith(base + '.bak.'))
    cur_sha = sha256_file(target)
    print('=' * 78)
    print('24000 v3 · rollback  %s' % target)
    print('=' * 78)
    print('当前             : %d B  sha256=%s' % (os.path.getsize(target), cur_sha))
    print('manifest         : %s' % (mpath or '无'))
    print('备份             : %d 个 %s' % (len(cands), ', '.join(cands) if cands else ''))
    if not cands:
        die('没有备份可回滚：%s' % (base + '.bak.*'))

    want = (manifest or {}).get('original_sha256')
    pick = None
    for n in reversed(cands):
        path = os.path.join(d, n)
        h = sha256_file(path)
        if want and h == want:
            pick = (n, h, '与 manifest 的原始 sha256 一致')
            break
        if not want:
            try:
                if BLOCK_BEGIN not in read_text(path):
                    pick = (n, h, '不含 v3 托管块（原始文件）')
                    break
            except Exception:
                continue
    if pick is None:
        n = cands[-1]
        pick = (n, sha256_file(os.path.join(d, n)),
                '** 没找到与原始 sha256 匹配的备份，取最新 **')
        if not a.force:
            die('无法确认最新备份就是原始文件（sha256 不匹配）。\n'
                '  用了 --force 才会强行恢复：%s' % os.path.join(d, n))

    name, have, why = pick
    src = os.path.join(d, name)
    if a.dry_run:
        print('[dry-run] 会恢复 %s <- %s（%s）' % (target, src, why))
        print('[dry-run] 恢复后 sha256 应为 : %s' % have)
        print('[dry-run] 没有写入任何文件')
        return 0

    shutil.copy2(src, target)
    after = sha256_file(target)
    ok_sha = (have == after) and (want is None or after == want)
    baseline_match = (after == BASELINE_SHA256)
    try:
        compile(read_text(target), target, 'exec')
        comp = 'OK'
    except SyntaxError as e:
        comp = 'FAILED: %s' % e
        ok_sha = False
    print('恢复自           : %s（%s）' % (src, why))
    print('恢复后 sha256    : %s' % after)
    print('manifest 原始    : %s' % (want or '（无 manifest）'))
    print('sha256 一致      : %s' % ('YES' if ok_sha else 'NO'))
    print('== 官方基线 sha256: %s（%s）'
          % ('YES' if baseline_match else 'NO', BASELINE_SHA256))
    print('compile          : %s' % comp)
    ok = ok_sha and comp == 'OK'
    print('ROLLBACK: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def cmd_dump_config(a, target=None):
    cfg = dict(DEFAULT_CONFIG)
    print('# 默认配置（存成 %s 即可生效，不需要重启 bridge）' % CONFIG_FILE)
    print(json.dumps(cfg, ensure_ascii=False, indent=1))
    print()
    print('# 改成 9 条学院地点（官方 32 级号就是 9 条；新号若因学院崩用这个 A/B）：')
    alt = dict(cfg)
    alt['locations'] = [{'LocationId': L, 'Rank': 1, 'Exp': 0}
                        for L in [1, 7, 11, 12, 13, 15, 16, 17, 19]]
    print(json.dumps(alt, ensure_ascii=False, indent=1))
    return 0


# ================================================================ main
def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True, description=__doc__.splitlines()[0])
    ap.add_argument('--target', default=None, help='account_auth_probe.py（默认自动定位线上路径）')
    ap.add_argument('--engine', default=None, help='gen24000.py 路径（默认与补丁同目录）')
    ap.add_argument('--manifest', default=None, help='manifest 路径（默认 bapatch/logs 或目标同级）')
    ap.add_argument('--apply', action='store_true', help='应用补丁')
    ap.add_argument('--verify', action='store_true', help='打印分支 + 渲染一次 + 7 项结构核对')
    ap.add_argument('--rollback', action='store_true', help='从备份恢复并校验 sha256')
    ap.add_argument('--dry-run', action='store_true', help='只打印将要做的改动，不写文件')
    ap.add_argument('--force', action='store_true', help='--rollback 时允许 sha256 不匹配也恢复')
    ap.add_argument('--allow-other-baseline', action='store_true',
                    help='目标 sha256 不是已知基线时也允许 --apply')
    ap.add_argument('--dump-config', action='store_true', help='打印 24000 运行配置样例')
    ap.add_argument('--account-id', type=int, default=None, help='--verify 用这个账号')
    ap.add_argument('--mxtoken', default=None, help='--verify 用这个 MxToken')
    a = ap.parse_args(argv)

    mode = 'dump-config' if a.dump_config else (
        'rollback' if a.rollback else
        'verify' if a.verify else
        'apply' if (a.apply or a.dry_run) else None)
    if mode is None:
        ap.error('必须给 --apply / --verify / --rollback / --dry-run 之一（防止误跑写文件）')

    if mode == 'dump-config':
        return cmd_dump_config(a)
    if mode == 'rollback':
        target = resolve_target(a.target)
        guard_write(target)
        return cmd_rollback(a, target)

    target = resolve_target(a.target)
    if mode == 'apply' and not a.dry_run:
        # --dry-run 是只读的：可以直接对 _baseline 预演，不写任何文件
        guard_write(target)
    engine_path, engine = load_engine(a.engine)
    a.engine_path = engine_path
    if mode == 'verify':
        return cmd_verify(a, engine, target)
    return cmd_apply(a, engine, target)


if __name__ == '__main__':
    sys.exit(main())
