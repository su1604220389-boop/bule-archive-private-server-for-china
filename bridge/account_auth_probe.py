#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""account_auth_probe.py v6 -- /api/* bridge.

Modes (file /www/wwwroot/bapatch/cn_bridge_mode.txt):
    bridge   : handle via decrypt / synthesize path
    forward  : raw passthrough to 127.0.0.1:5000 with original URI

Experiment switch (file /www/wwwroot/bapatch/cn_bridge_exp.txt):
    ''                    : normal (synthetic Account_Auth, plain response)
    'plain'               : same as ''
    'resultstate0'        : inject ResultState:0 into Account_Auth response
    'resultstate1'        : inject ResultState:1
    'experror'            : reply the legacy Error envelope, no Shittim call
    'decrypt+plain'       : decrypt real client request, inject SessionKey, plain response
    'decrypt+encresp1'    : ... encrypted response, whole JSON inside ciphertext
    'decrypt+encresp2'    : ... encrypted response, fragment only, Protocol as NUMBER outside
    'decrypt+encresp3'    : ... encrypted response, fragment only, Protocol as NAME outside
"""
import http.server
import socketserver
import json
import re
import time
import base64
import os
import struct
import gzip
import threading
import urllib.request
import urllib.error
import hashlib
import sys

sys.path.insert(0, '/www/wwwroot/bapatch/tools')
import cn_cipher  # noqa: E402
import cn_wire  # noqa: E402
import cn_inner  # noqa: E402
import cn_inner27  # noqa: E402
import cn_nick  # noqa: E402

# ============================ account service (L2) ============================
ACCT_SVC_FILE = '/www/wwwroot/bapatch/cn_account_svc.txt'
ACCT_LOG = '/www/wwwroot/bapatch/logs/acct_svc.log'
ACCT_DB = os.environ.get('BA_ACCT_DB', '/www/wwwroot/bapatch/data/accounts.db')

_SVC_INST = None
_LAST_SID = None


# ==== BEGIN 90004-PATCH v1 (from work/ba/server/deploy/dto90004.py)
# 本块由 work/ba/server/deploy/patch_90004.py --apply 生成，不要手改。
# 改逻辑请改 work/ba/server/deploy/dto90004.py，然后重新 --apply（幂等）。

import json
import os

P90004_DATA_KEYS = (
    "Notices", "Events", "Issues", "Banners", "GachaProbabilityDisplay",
    "GuidePopup", "GachaPeriodDisplay", "RaidPeriodDisplay", "Survey",
)

P90004_NULL_KEYS = ("GachaPeriodDisplay", "RaidPeriodDisplay", "Survey")

P90004_LIST_KEYS = ("Notices", "Events", "Issues", "Banners",
                    "GachaProbabilityDisplay", "GuidePopup")

P90004_NOTICE_FIELDS = (
    ("NoticeId", "int", True),
    ("StartDate", "str", True),
    ("EndDate", "str", True),
    ("Url", "str", True),
    ("Title", "str", True),
    ("DisplayOrder", "int", True),
)

P90004_EVENT_FIELDS = P90004_NOTICE_FIELDS

P90004_BANNER_FIELDS = (
    ("BannerId", "int", True),
    ("StartDate", "str", True),
    ("EndDate", "str", True),
    ("CdnUrl", "str", True),
    ("LinkedLobbyBannerId", "int", False),
    ("BannerType", "int", False),
    ("LinkUrl", "str", True),
    ("SurveyId", "int", True),
    ("BannerDisplayType", "int", True),
    ("CreateTime", "str", True),
)

P90004_GACHA_FIELDS = (
    ("GachaProbabilityDisplayId", "int", True),
    ("Url", "str", True),
    ("LinkedLobbyBannerId", "int", True),
    ("GachaDisplayTag", "int", True),
)

P90004_OPS_PATHS = (
    "/www/wwwroot/bapatch/_ba_state/90004_ops.json",
    "/www/wwwroot/bapatch/90004_ops.json",
)

def _p90004_int(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        s = v.strip()
        try:
            return int(s)
        except Exception:
            return 0
    return 0

def _p90004_str(v):
    if isinstance(v, str):
        return v
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)

def _p90004_items(raw, fields):
    """把任意脏数据投影成「字段白名单 + 类型强转 + 官方键序」的列表。

    白名单的意义：运营数据里多写的键不会漏到客户端（多键 = 结构错）；
    可选字段缺省时**整个键不出现**（官方 2/7 条 banner 就是这样）。
    """
    if not isinstance(raw, list):
        return []
    out = []
    for it in raw:
        if not isinstance(it, dict):
            continue
        row = {}
        for name, kind, need in fields:
            if name in it and it[name] is not None:
                row[name] = _p90004_int(it[name]) if kind == "int" else _p90004_str(it[name])
            elif need:
                row[name] = 0 if kind == "int" else ""
            # 可选且缺 → 不出现（proto3 presence 语义）
        out.append(row)
    return out

def build_90004_management_data(session_key, ticks, request_id, ops=None):
    """返回官方形状的 90004 响应（6 个顶层键，Data 是 9 键 dict）。

    session_key : {"AccountServerId": int, "MxToken": str}   取不到时传 {} 或 None
    ticks       : ServerTimeTicks（.NET 100ns）
    request_id  : 必须与 HTTP 响应头 requestid 同值（官方逐字节相同）
    ops         : 运营数据 dict，可残缺；None = 新号（4 个列表全空 + 3 个 null）
    """
    sk = session_key if isinstance(session_key, dict) else {}
    ops = ops if isinstance(ops, dict) else {}

    data = {}
    data["Notices"] = _p90004_items(ops.get("Notices"), P90004_NOTICE_FIELDS)
    data["Events"] = _p90004_items(ops.get("Events"), P90004_EVENT_FIELDS)
    data["Issues"] = _p90004_items(ops.get("Issues"), ())
    data["Banners"] = _p90004_items(ops.get("Banners"), P90004_BANNER_FIELDS)
    data["GachaProbabilityDisplay"] = _p90004_items(
        ops.get("GachaProbabilityDisplay"), P90004_GACHA_FIELDS)
    data["GuidePopup"] = _p90004_items(ops.get("GuidePopup"), ())
    # 三个恒 null（不是 False、不是 {}）
    data["GachaPeriodDisplay"] = None
    data["RaidPeriodDisplay"] = None
    data["Survey"] = None

    return {
        "Protocol": 90004,
        "SessionKey": {"AccountServerId": _p90004_int(sk.get("AccountServerId")),
                       "MxToken": _p90004_str(sk.get("MxToken"))},
        "ServerTimeTicks": _p90004_int(ticks),
        "ServerNotification": 0,
        "RequestId": _p90004_str(request_id),
        "Data": data,
    }

def load_90004_ops(path=None):
    """读运营数据：显式 path 优先；否则扫 P90004_OPS_PATHS。失败一律返回 None。"""
    cands = [path] if path else list(P90004_OPS_PATHS)
    for p in cands:
        if not p or not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8") as fh:
                obj = json.load(fh)
        except Exception:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("Data"), dict):
            obj = obj["Data"]          # 容忍直接把整个响应存进去
        if isinstance(obj, dict):
            return obj
    return None

def data_key_report(obj):
    """给日志/验收用：Data 的键数 + 各列表长度。"""
    d = obj.get("Data") or {}
    return {"data_keys": len(d),
            "Notices": len(d.get("Notices") or []),
            "Events": len(d.get("Events") or []),
            "Issues": len(d.get("Issues") or []),
            "Banners": len(d.get("Banners") or []),
            "GachaProbabilityDisplay": len(d.get("GachaProbabilityDisplay") or []),
            "GuidePopup": len(d.get("GuidePopup") or []),
            "nulls": [k for k in P90004_NULL_KEYS if d.get(k, "missing") is None]}

# ==== END 90004-PATCH v1 ====

def acct_svc_on():
    """1 = enabled (default), 0 = disabled."""
    try:
        return open(ACCT_SVC_FILE).read().strip() == '1'
    except Exception:
        return True


def acct_log(msg):
    try:
        with open(ACCT_LOG, 'a') as f:
            f.write('%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg))
    except Exception:
        pass


def acct_fallback(msg):
    """Never fail silently: every fallback leaves a trace."""
    acct_log('[acct] fallback to hardcoded: ' + msg)


def _svc():
    global _SVC_INST
    if _SVC_INST is None:
        os.environ.setdefault('BA_ACCOUNT_DB', ACCT_DB)
        import account_service as _m
        _SVC_INST = _m.default_service()
        _SVC_INST.init_schema()
    return _SVC_INST


_FRAG_TLS = threading.local()

# >>> BANREPLY2 FIX-C BEGIN >>>
# [修 3] 请求身份不再用 id(rec)，改用**单调递增的请求序号**。
#
# 缺陷：`_FRAG_TLS.seq = id(rec)` 用内存地址当请求身份。服务端是 ThreadingTCPServer
#   （:5005-5006，一个 keep-alive 连接一个线程），`_FRAG_TLS` 因此跨该连接上的多次请求存活；
#   而 rec 每请求新建（:2763），前一个 rec 释放后新 rec 极容易拿到同一地址
#   -> `_req_dict` 的 `seq == id(rec)` 假命中 -> 本请求读到上一个请求的 fragment（串号）。
#
# 修法：每个 rec 第一次被问到时，从全局计数器领一个号并缓存在 rec['_req_seq']；
#   计数器只增不减（CPython int 无溢出），所以"后来的请求"的号**永远不可能**等于
#   "先前请求"的号，残留的 `_FRAG_TLS.seq` 与新 rec 的号必然不等。
#   号是 int，`_FRAG_TLS.seq` 初值/复位值 None 与之比较恒为 False（与原语义一致）。
_REQ_SEQ_LOCK = threading.Lock()
_REQ_SEQ_NEXT = [0]


def _req_seq(rec):
    """rec -> 本请求的单调序号（首次领取后缓存在 rec['_req_seq']）。

    非 dict / 任何异常 -> 返回一个**全新 object()**：它只会等于它自己，
    因此写方与读方各拿一个时必然不等（宁可这一段拿不到 fragment，也绝不串号）。
    """
    try:
        if isinstance(rec, dict):
            v = rec.get('_req_seq')
            if isinstance(v, int) and v > 0:
                return v
            with _REQ_SEQ_LOCK:
                _REQ_SEQ_NEXT[0] += 1
                v = _REQ_SEQ_NEXT[0]
            rec['_req_seq'] = v
            return v
    except Exception:
        pass
    return object()


# [修 2] 原始 DevId / DeviceUniqueId 只活在 TLS（与 _FRAG_TLS 同生命周期、同一个请求序号）。
#
# 为什么不放 rec['_devid_raw']：rec 会被 _log 整个 json.dumps 落进 api_all_requests.log
#   （:2717-2722），放进 rec 就等于把真实 DevId 写进日志 —— 那正是要求里禁止的。
#   TLS 天然不进任何 req 的状态转储，且同一请求内多次 _req_dict 都能取到。
_DEVID_TLS = threading.local()
_DEVID_MASK_MARKERS = ('****', '(len=', 'sha8=')


def _devid_plain(v):
    """身份字段取值的唯一闸门：只接受"看起来是原始值"的字符串。

    mask_secret(keep=(0,0)) 的产物形如 '****(len=9,sha8=1a2b3c4d)'：非空、但不是身份。
    含脱敏标记的 -> ''。
    """
    try:
        if not isinstance(v, str):
            return ''
        s = v.strip()
        if not s:
            return ''
        for m in _DEVID_MASK_MARKERS:
            if m in s:
                return ''
        return s
    except Exception:
        return ''


def _devid_raw_put(rec, devid, duid):
    """记下本请求的原始值（只进 TLS，绝不进 rec / 日志 / 落盘）。"""
    try:
        _DEVID_TLS.seq = _req_seq(rec)
        _DEVID_TLS.devid = devid if isinstance(devid, str) else ''
        _DEVID_TLS.duid = duid if isinstance(duid, str) else ''
    except Exception:
        try:
            _DEVID_TLS.seq = None
            _DEVID_TLS.devid = ''
            _DEVID_TLS.duid = ''
        except Exception:
            pass


def _devid_raw_get(rec):
    """-> (devid, duid) 原始值；不是本请求写进去的 -> ('', '')。"""
    try:
        if getattr(_DEVID_TLS, 'seq', None) is None:
            return '', ''
        if _DEVID_TLS.seq == _req_seq(rec):
            return (getattr(_DEVID_TLS, 'devid', '') or '',
                    getattr(_DEVID_TLS, 'duid', '') or '')
    except Exception:
        pass
    return '', ''


def _devid_guard(req, rec=None):
    """identify() 之前最后一道闸：DevId / DeviceUniqueId 只能是**真实值**或**空串**。

    返回同一个 dict（就地清洗）。只记"发生过清洗"这个判定，不记值。
    """
    try:
        if not isinstance(req, dict):
            return req
        blocked = False
        for k in ('DevId', '<REDACTED_DEVID>'):
            v = req.get(k)
            if not isinstance(v, str):
                continue
            c = _devid_plain(v)
            if c != v:
                req[k] = c
                blocked = True
        if blocked and isinstance(rec, dict):
            rec['devid_mask_blocked'] = True
        return req
    except Exception:
        return req
# <<< BANREPLY2 FIX-C END <<<


def _fallback_dev_id():
    # [PATCH-PY-20261118-P5] 兜底号 314816420 -> '9000000001'（卡号值域之外，永不撞真实卡）。
    #   BA_FALLBACK_DEV_ID 显式给了合法值时仍然优先，与基线一致。
    v = (os.environ.get('BA_FALLBACK_DEV_ID') or '').strip()
    if v.isdigit() and 0 < len(v) <= 20 and int(v) > 0:
        return v
    return '9000000001'


FALLBACK_DEV_ID = _fallback_dev_id()


def _req_dict(rec):
    """Best-effort json of the decrypted request fragment."""
    _frag_tls = None
    try:
        # [修 3] id(rec) -> _req_seq(rec)：单调序号，永不复用（见 _req_seq）
        if getattr(_FRAG_TLS, 'seq', None) == _req_seq(rec):
            _frag_tls = getattr(_FRAG_TLS, 'v', None)
        _FRAG_TLS.v = None
        _FRAG_TLS.seq = None
    except Exception:
        _frag_tls = None
    frag = (_frag_tls or '').strip() if isinstance(_frag_tls, str) else ''
    if isinstance(rec, dict):
        rec['req_devid_src'] = 'fragment' if frag else 'fallback'
    if not frag:
        frag = (rec.get('req_frag_head') or '').strip()
    if not frag:
        return {}
    body = frag.lstrip(',')
    if not body.startswith('{'):
        body = '{' + body
    if not body.endswith('}'):
        body = body + '}'
    try:
        _d = json.loads(body)
    except Exception:
        return {}
    devid_stash(rec, _d)
    return _d if isinstance(_d, dict) else {}


def acct_apply_to_auth(inner, rec):
    """Replace AccountDB + SessionKey with the real per-account values."""
    global _LAST_SID
    if not acct_svc_on():
        rec['acct_svc'] = 'off'
        return inner
    try:
        svc = _svc()
        req = _req_dict(rec)
        if not req:
            # >>> BANREPLY2 FIX-B BEGIN >>>
            # 兜底 req 里的身份字段只接受**原始值**：
            #   ① 本请求早先 _req_dict 解析成功过时，原始 DevId 在 _DEVID_TLS（不进 rec / 不进日志）；
            #   ② rec['req_DevId'] / rec['req_DeviceUniqueId'] 是 devid_stash:649/651 的脱敏产物
            #      （'****(len=9,sha8=…)'），**非空但不是身份** —— 原样喂给 identify() 会被
            #      当成真 DevId 建出垃圾账号（每来一次多一行 '****…' 的账户）。
            #   两条都拿不到 -> 空串：identify() 随后走它自己的"无稳定身份键"既有分支。
            _dv_raw, _du_raw = _devid_raw_get(rec)
            _dv = _devid_plain(_dv_raw) or _devid_plain(rec.get('req_DevId'))
            _du = _devid_plain(_du_raw) or _devid_plain(rec.get('req_DeviceUniqueId'))
            req = {'DevId': _dv,
                   'DeviceUniqueId': _du,
                   'Token': _devid_plain(rec.get('req_Token'))}
            try:
                if isinstance(rec, dict):
                    rec['devid_fix'] = ('raw-tls' if _devid_plain(_dv_raw)
                                        else ('raw-recv' if _dv else 'none'))
                    rec['devid_fix_empty'] = not (_dv or _du)
            except Exception:
                pass
            # 只记判定结果，不记值
            acct_log('[devid] fallback req: DevId=%s DeviceUniqueId=%s（脱敏值一律不作身份）'
                     % ('raw' if _dv else "''", 'raw' if _du else "''"))
            # <<< BANREPLY2 FIX-B END <<<
        req = _devid_guard(req, rec)      # [修 2] 任何路径都不许把 '****…' 交给 identify()
        ident = svc.identify(req)
        # [PATCH-PY-20261118-P4] 绝不凭未知 dev_id 建号：未知/无行一律退兜底账号
        # [PATCH-PY-20261118-P5] 重新施加账号层修正：请求包自带可信身份
        #   （dev_id_source in ('DevId','<REDACTED_DEVID>')）且库里查无此行 ⇒ 这是真·新玩家
        #   ⇒ acct_id_src='create'，按真 DevId 建号。其余一切情况（身份不可信 / 查询未知 /
        #   查不到但来源不可信）仍然一律退兜底号 —— P4 的"绝不凭未知 dev_id 建号"不变。
        try:
            _dev = (getattr(ident, 'dev_id', '') or '').strip()
            _fb = str(FALLBACK_DEV_ID)
            _src = (getattr(ident, 'dev_id_source', None) or '')
            _trusted = _src in ('DevId', '<REDACTED_DEVID>')
            _exists = None
            if _dev:
                try:
                    _exists = svc.get_account_by_dev_id(_dev) is not None
                except Exception:
                    _exists = None                      # 未知
            if _exists is True:
                rec['acct_id_src'] = 'exact'
            elif _exists is False and _trusted:
                rec['acct_id_src'] = 'create'           # 可信身份 + 无行 ⇒ 新卡/新玩家，建号
            else:
                ident.dev_id = _fb                  # 身份不可信/未知 ⇒ 退兜底号（不吞真实 DevId）
                ident.dev_id_source = (_src or 'DevId') + '+retarget'
                rec['acct_id_retarget'] = True
                rec['acct_id_src'] = 'retarget-fallback'
        except Exception as e:
            rec['acct_id_src'] = 'resolve-err:' + type(e).__name__
            try:
                ident.dev_id = str(FALLBACK_DEV_ID)     # 兜底中的兜底
                rec['acct_id_retarget'] = True
            except Exception:
                pass
        acct = svc.get_or_create_account(ident)
        sess = svc.issue_session_key(acct)
        adb = svc.build_account_db_for(acct)
        sk = sess.to_dict() if hasattr(sess, 'to_dict') else sess
        inner['AccountDB'] = adb
        inner['SessionKey'] = sk
        _LAST_SID = adb.get('ServerId')
        rec['acct_svc'] = 'on'
        rec['acct_server_id'] = _LAST_SID
        rec['acct_mxtoken'] = mask_secret(sk.get('MxToken'))
    except Exception as e:
        acct_fallback('%s: %s' % (type(e).__name__, e))
        rec['acct_svc'] = 'fallback:' + type(e).__name__
        rec['acct_err'] = repr(e)
    return inner


def acct_writeback(rec, **fields):
    """Persist nickname / call_name. Write failure must NOT affect the response."""
    if not acct_svc_on():
        return
    try:
        sid = _LAST_SID
        if not sid:
            rec['acct_wb'] = 'skip:no-session'
            return
        _svc().update_account(int(sid), **fields)
        rec['acct_wb'] = 'ok:%s' % ','.join(fields)
    except Exception as e:
        acct_fallback('writeback %s: %s: %s' % (list(fields), type(e).__name__, e))
        rec['acct_wb'] = 'err:' + type(e).__name__
        rec['acct_wb_err'] = repr(e)


LOG         = '/www/wwwroot/bapatch/logs/api_all_requests.log'

# [PATCH-PY-20261118v2] 请求体上限 + 日志脱敏
import hashlib as _hashlib

MAX_REQUEST_BODY = 4194304
SENSITIVE_KEYS = ("mx_token", "mxtoken", "<REDACTED_TOKEN>", "session_key", "<REDACTED_TOKEN>",
                  "token", "<REDACTED_TOKEN>", "req_iv", "devid", "<REDACTED_DEVID>", "password")


def mask_secret(v, keep=(4, 4)):
    if v is None:
        return None
    s = str(v)
    if len(s) <= keep[0] + keep[1]:
        return "*" * len(s)
    _tail = s[-keep[1]:] if keep[1] > 0 else ''
    return "%s****%s(len=%d,sha8=%s)" % (s[:keep[0]], _tail, len(s),
                                           _hashlib.sha256(s.encode()).hexdigest()[:8])


def _parse_content_length(raw):
    if raw is None or str(raw).strip() == "":
        return 0, "missing Content-Length"
    try:
        n = int(str(raw).strip())
    except Exception:
        return 0, "non-numeric Content-Length"
    if n < 0:
        return 0, "negative Content-Length"
    if n > MAX_REQUEST_BODY:
        return 0, "Content-Length %d exceeds cap %d" % (n, MAX_REQUEST_BODY)
    return n, ""

MODE_FILE   = '/www/wwwroot/bapatch/cn_bridge_mode.txt'
FORCE_FILE  = '/www/wwwroot/bapatch/cn_bridge_force_reauth.txt'
EXP_FILE    = '/www/wwwroot/bapatch/cn_bridge_exp.txt'
CN_RESP_FILE = '/www/wwwroot/bapatch/cn_resp_format.txt'
CN_FIELD_PATCH_FILE = '/www/wwwroot/bapatch/cn_field_patch.txt'
CN_CANARY_FILE = '/www/wwwroot/bapatch/cn_canary.txt'
CN_HASH_FILE = '/www/wwwroot/bapatch/cn_hash_mode.txt'
CN_PROTO_VAL_FILE = '/www/wwwroot/bapatch/cn_proto_val.txt'
CN_FLATTEN_FILE = '/www/wwwroot/bapatch/cn_flatten_keys.txt'
CN_PACKET_WRAP_FILE = '/www/wwwroot/bapatch/cn_packet_wrap.txt'
CN_WRAP_MODE_FILE = '/www/wwwroot/bapatch/cn_wrap_mode.txt'
CN_INNER_MIN_FILE = '/www/wwwroot/bapatch/cn_inner_min.txt'
CN_INNER_SRC_FILE = '/www/wwwroot/bapatch/cn_inner_src.txt'
CN_REQUESTID_FILE = '/www/wwwroot/bapatch/cn_requestid_mode.txt'
NAMES_FILE  = '/www/wwwroot/bapatch/tools/protocol_names.txt'
TARGET_BASE = 'http://127.0.0.1:5000'
GATEWAY     = 'http://127.0.0.1:5000/api/gateway'
BOUNDARY    = '----cnbridge'

UID   = '314816420'
TOKEN = '<REDACTED_TOKEN>'
ENTER_TICKET = base64.b64encode(('%s/%s' % (UID, TOKEN)).encode()).decode()
CLIENT_KEY = base64.b64encode(bytes(range(32))).decode()
CLIENT_IV  = base64.b64encode(bytes(range(16))).decode()

HOP = ('host', 'content-length', 'connection', 'accept-encoding', 'transfer-encoding')

BUILTIN_NAMES = [
    "Account_CheckNexon", "Account_Auth", "Account_Auth2", "Account_Create",
    "Account_VerifyForYostar", "Account_CheckYostar", "Account_GetTutorial",
    "Account_SetTutorial", "Account_PassCheck", "Account_Nickname",
    "Account_GetIdCardInformation", "Account_Logout",
    "Queuing_GetCryptoKeys", "Queuing_GetAuthTicket", "Queuing_GetTicket",
    "Queuing_Ping", "Queuing_GetTicketGL", "Queuing_ProcessWaitingQueue",
    "Queuing_GetWaitingQueue",
    "NetworkTime_Sync", "Session_Info", "System_Version", "System_ServerTime",
    "Player_GetSetting", "Player_SetSetting", "Content_GetList", "Loading_Complete",
    "Shop_List", "Shop_BuyGoods", "Character_List", "Mission_List", "Mail_List",
    "Mail_Receive", "Cafe_GetInfo", "Clan_List", "Friend_GetList", "Raid_GetInfo",
    "TimeAttack_GetInfo", "MomoTalk_GetOutline", "Scenario_List", "Sticker_List",
    "Event_GetList", "Campaign_GetList",
]

NUM_TO_NAME = {}   # filled from our own knowledge of numbers we have seen



# [PATCH-PY-20261118-f1b] 按方法分流 Content-Length + 有界 chunked 读取
def _read_chunked(stream, cap):
    total = 0
    out = bytearray()
    while True:
        line = stream.readline(128)
        if not line:
            raise ValueError("chunked eof")
        try:
            size = int(line.split(b";", 1)[0].strip(), 16)
        except Exception:
            raise ValueError("bad chunk size")
        if size == 0:
            while True:
                t = stream.readline(128)
                if t in (b"\r\n", b"\n", b""):
                    break
            return bytes(out)
        total += size
        if total > cap:
            raise OverflowError("chunked body exceeds cap %d" % cap)
        data = stream.read(size)
        if len(data) != size:
            raise ValueError("short chunk")
        out += data
        stream.read(2)


def _read_request_body(handler, max_body):
    """-> (body|None, http_code|None, err_msg|None)"""
    method = (handler.command or "").upper()
    te = (handler.headers.get("Transfer-Encoding") or "").lower()
    cl_raw = handler.headers.get("Content-Length")
    if "chunked" in te:
        try:
            return _read_chunked(handler.rfile, max_body), None, None
        except OverflowError as e:
            return None, 413, str(e)
        except Exception:
            return None, 400, "bad chunked body"
    try:
        n, err = _parse_content_length(cl_raw)
    except Exception:
        n, err = 0, "bad Content-Length"
    if err:
        if err == "missing Content-Length" and method in ("GET", "HEAD", "OPTIONS"):
            n, err = 0, ""
        elif err.startswith("Content-Length") and "exceeds cap" in err:
            return None, 413, err
        else:
            return None, 400, err
    try:
        body = handler.rfile.read(n) if n else b""
    except Exception:
        return None, 400, "read failed"
    return body, None, None

def b32md5(name):
    return base64.b32encode(hashlib.md5(name.encode('utf-16-le')).digest()).decode().rstrip('=')


NAME_TABLE = {}

# tokens verified from the client's own captured requests (base32(md5(utf-16-le(name))))
EXTRA_TOKENS = {
    'AHTQLQI65FWJGGGK4KL5AEF57A': 'Account_Auth',
    'GVDSNCHUMIOS44NDTZM6ZPDDVQ': 'Account_Nickname',
    'K3SF6XS7VK7JFL7T2M2WFELUSY': 'Account_CallName',
    'FZGO2J3INCGSND5AGKDLB7EBSY': 'Account_CheckNexon',
    'P3OMQZD2FXV7XXEGA7ETCXIJ4Q': 'Account_LoginSync',
}
# >>> BAPATCH-NAME-FIX v1 BEGIN >>> (deploy/fix_name_unknown.py)
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

# >>> BAPATCH-NAMETOKEN v1 BEGIN >>> (deploy/fix6_nametoken.py)
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

# >>> BAPATCH-BILLINGBLOCK v1 BEGIN >>>
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

# >>> BAPATCH-1017RELAY v1 BEGIN >>>
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

# >>> BAPATCH-DEVID v1 BEGIN >>>
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
        if not isinstance(d, dict) or not isinstance(rec, dict):
            return
        dv = d.get('DevId')
        du = d.get('DeviceUniqueId')
        # [修 2] 原始值另存 TLS（不进 rec / 不进日志）；下面两行的脱敏值继续按基线写 rec，
        #        日志里的 req_devid_len / req_devid_sha8 诊断能力一字不减。
        _devid_raw_put(rec, (dv.strip() if isinstance(dv, str) else ''),
                       (du.strip() if isinstance(du, str) else ''))
        if isinstance(dv, str) and dv.strip():
            rec['req_DevId'] = mask_secret(dv.strip(), keep=(0, 0))
        if isinstance(du, str) and du.strip():
            rec['req_DeviceUniqueId'] = mask_secret(du.strip(), keep=(0, 0))
        _dv = dv.strip() if isinstance(dv, str) and dv.strip() else ''
        rec['req_devid_len'] = len(_dv)
        rec['req_devid_sha8'] = hashlib.sha256(_dv.encode()).hexdigest()[:8] if _dv else None
    except Exception:
        pass

# <<< BAPATCH-DEVID v1 END <<<

# >>> BAPATCH-DEDUP v1 BEGIN >>>
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

# >>> BAPATCH-DEDUP v1 RELAYPATH BEGIN >>>
def dedup_key_obj(name, req):
    if not isinstance(req, dict):
        return None
    for k in ('PurchaseOrderId', 'OrderNo', 'OrderId', 'ShopCashId'):
        v = req.get(k)
        if isinstance(v, (int, str)) and str(v) not in ('', '0'):
            return '%s|%s=%s' % (name, k, v)
    sk = req.get('SessionKey')
    if isinstance(sk, dict) and sk.get('AccountServerId'):
        return '%s|acct=%s' % (name, sk.get('AccountServerId'))
    return None


def dedup_fetch(key, name, rec):
    try:
        if not dedup_on() or name not in DEDUP_NAMES or not key:
            return None
        hit = dedup_lookup(key)
        if isinstance(rec, dict):
            rec['dedup_key'] = key
            rec['dedup_hit'] = hit is not None
        return hit
    except Exception:
        return None


def dedup_put(key, name, payload, rec):
    try:
        if not dedup_on() or name not in DEDUP_NAMES or not key or payload is None:
            return
        dedup_store(key, payload)
        if isinstance(rec, dict):
            rec['dedup_stored'] = True
    except Exception:
        pass
# <<< BAPATCH-DEDUP v1 RELAYPATH END <<<




def load_names():
    global NAME_TABLE
    t = {}
    names = list(BUILTIN_NAMES)
    try:
        for line in open(NAMES_FILE):
            n = line.strip()
            if n and not n.startswith('#'):
                names.append(n)
    except Exception:
        pass
    for n in set(names):
        try:
            t[b32md5(n)] = n
        except Exception:
            pass
    NAME_TABLE = t
    return len(t)


def mode():
    try:
        return open(MODE_FILE).read().strip() or 'bridge'
    except Exception:
        return 'bridge'


HTTP_SUFFIXES = ('+http500', '+http200empty', '+http404', '+http200')


def _raw_exp():
    try:
        return open(EXP_FILE).read().strip()
    except Exception:
        return ''


def exp_flag():
    v = _raw_exp()
    for suf in HTTP_SUFFIXES:
        if v.endswith(suf):
            return v[:-len(suf)]
    return v


def http_override():
    v = _raw_exp()
    for suf in HTTP_SUFFIXES:
        if v.endswith(suf):
            return suf[1:]
    return None


def cn_resp_format():
    # 'shittim' (default): {"protocol":"Account_Auth","packet":"<json string>"}
    # 'cn_envelope'      : {"protocol":"<base32 md5>","packet":"<b64 [u32 len][gzip(json)]>"}
    try:
        v = open(CN_RESP_FILE).read().strip()
    except Exception:
        return 'shittim'
    return v or 'shittim'


def cn_field_patch_mode():
    # 'off' (default) | 'on' | 'on_alt'
    # on     : FunctionClose = []
    # on_alt : FunctionClose = false
    try:
        v = open(CN_FIELD_PATCH_FILE).read().strip()
    except Exception:
        return 'off'
    return v or 'off'


def apply_field_patch(obj, rec=None):
    # Adds CN-only AccountAuthResponse fields that Shittim never emits.
    # Types are INFERRED (see report/41 section 3.1); only missing keys are added.
    m = cn_field_patch_mode()
    if m not in ('on', 'on_alt') or not isinstance(obj, dict):
        return obj
    func_close = {} if m == 'on' else []
    defaults = {
        # AccountAuthResponse fields we never emitted
        'Desc': '',
        'FunctionClose': func_close,
        'DailyRecordDBs': [],
        'MinimumVersion': 0,
        'IsDevelopment': False,
        'BattleValidation': False,
        'UpdateRequired': False,
        # ResponsePacket base-class collections we never emitted
        'MissionProgressDBs': [],
        'EventMissionProgressDBDict': {},
        'BattlePassMissionProgressDBDict': {},
    }
    added = []
    for k, v in defaults.items():
        if k not in obj:
            obj[k] = v
            added.append(k)
    if rec is not None:
        rec['field_patch'] = m
        rec['field_patch_added'] = added
    return obj


def cn_requestid_mode():
    # 'random' (default) | 'echo'  (echo = reuse a UUID found in the client request, if any)
    try:
        v = open(CN_REQUESTID_FILE).read().strip()
    except Exception:
        return 'random'
    return v or 'random'


UUID_RE = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')


def pick_requestid(rec):
    if cn_requestid_mode() == 'echo':
        frag = rec.get('req_frag_head') or ''
        m = UUID_RE.search(frag)
        if m:
            rec['requestid_source'] = 'echo-from-request'
            return m.group(0)
        rec['requestid_source'] = 'echo-fallback-random(no uuid in request)'
        return None
    rec['requestid_source'] = 'random'
    return None


def cn_inner_src():
    # 'shittim' (default) = today's Shittim-derived 38-key inner
    # 'spec26'            = report/49 CN DTO inner (26 keys incl _probe)
    try:
        v = open(CN_INNER_SRC_FILE).read().strip()
    except Exception:
        return 'shittim'
    return v or 'shittim'


def cn_inner_min_on():
    try:
        v = open(CN_INNER_MIN_FILE).read().strip()
    except Exception:
        return False
    return v == 'on'


MIN_KEEP = [
    # [BAPATCH-BANREPLY v1] Error 包的两个数据键必须留下，否则 cn_inner_min.txt=on 时
    # [BAPATCH-BANREPLY v1] 封禁包会被 apply_min_inner 剪成 {"Protocol":-1,...}（ErrorCode/BanReason 全丢）。
    'ErrorCode', 'BanReason',
    'Protocol', 'ServerTimeTicks', 'ServerNotification',
    'AccountId', 'AccountDB', 'SessionKey', 'EncryptedUID', 'CurrentVersion',
    'StaticOpenConditions',
    'MxToken', '<REDACTED_TOKEN>', 'ServerId',
    'Desc', 'FunctionClose', 'DailyRecordDBs', 'MinimumVersion', 'IsDevelopment',
    'BattleValidation', 'UpdateRequired', 'MissionProgressDBs',
    'EventMissionProgressDBDict', 'BattlePassMissionProgressDBDict',
    '_probe',
]


def apply_min_inner(obj, rec=None):
    if not cn_inner_min_on() or not isinstance(obj, dict):
        return obj
    out = {k: obj[k] for k in MIN_KEEP if k in obj}
    if rec is not None:
        rec['inner_min'] = True
        rec['inner_min_dropped'] = sorted(set(obj) - set(out))
    return out


def cn_wrap_mode():
    # 'existing' (default) keeps today's behaviour; 'cn_enc_b64' = real CN wire format
    try:
        v = open(CN_WRAP_MODE_FILE).read().strip()
    except Exception:
        return 'existing'
    return v or 'existing'


def cn_packet_wrap():
    # 'raw_gzip' (default, current): packet = base64([u32 len][gzip(inner)])
    # 'json_string'           : packet = json text of inner (no base64, no gzip)
    try:
        v = open(CN_PACKET_WRAP_FILE).read().strip()
    except Exception:
        return 'raw_gzip'
    return v or 'raw_gzip'


def cn_proto_val():
    # 'name' -> "Account_Auth"; 'token' -> base32 md5 form (default keeps current behaviour)
    try:
        v = open(CN_PROTO_VAL_FILE).read().strip()
    except Exception:
        return 'token'
    return v or 'token'


def cn_flatten_on():
    try:
        v = open(CN_FLATTEN_FILE).read().strip()
    except Exception:
        return False
    return v == 'on'


def apply_flatten(obj, rec=None):
    # Keep the nested SessionKey object AND add flat duplicates.
    # CN metadata has no 'SessionKey' key at all; SessionDB exposes MxToken flat.
    if not cn_flatten_on() or not isinstance(obj, dict):
        return obj
    sk = obj.get('SessionKey')
    if not isinstance(sk, dict):
        return obj
    added = []
    for k in ('MxToken', '<REDACTED_TOKEN>'):
        if k in sk and k not in obj:
            obj[k] = sk[k]
            added.append(k)
    sid = None
    adb = obj.get('AccountDB')
    if isinstance(adb, dict):
        sid = adb.get('ServerId')
    if sid is None:
        sid = obj.get('AccountServerId') or sk.get('AccountServerId')
    if sid is not None and 'ServerId' not in obj:
        obj['ServerId'] = sid
        added.append('ServerId')
    if rec is not None:
        rec['flatten_added'] = added
    return obj


def cn_hash_mode():
    # 'request' (default) echoes the client's own Hash back; 'off' does not.
    try:
        v = open(CN_HASH_FILE).read().strip()
    except Exception:
        return 'request'
    return v or 'request'


def cn_canary_on():
    # 'on' injects a plaintext-layer canary into the cn_envelope outer JSON.
    try:
        v = open(CN_CANARY_FILE).read().strip()
    except Exception:
        return False
    return v == 'on'


def want_force_reauth():
    return os.path.exists(FORCE_FILE)


def clear_force():
    try:
        os.remove(FORCE_FILE)
    except Exception:
        pass


def post_gateway(obj, timeout=40):
    mx = cn_cipher.build_mx(obj)
    body = (('--%s\r\nContent-Disposition: form-data; name="mx"; filename="p.mx"\r\n'
             'Content-Type: application/octet-stream\r\n\r\n') % BOUNDARY).encode() + mx \
           + ('\r\n--%s--\r\n' % BOUNDARY).encode()
    req = urllib.request.Request(GATEWAY, data=body, method='POST')
    req.add_header('Content-Type', 'multipart/form-data; boundary=%s' % BOUNDARY)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, ('{"error":%r}' % str(e)).encode()


def unwrap_gateway_response(raw):
    try:
        j = json.loads(raw.decode('utf-8', 'replace'))
    except Exception:
        return None, None
    pkt = j.get('packet')
    if isinstance(pkt, str):
        try:
            return j.get('protocol'), json.loads(pkt)
        except Exception:
            return j.get('protocol'), pkt
    return j.get('protocol'), pkt


class Session(object):
    def __init__(self):
        self.lock = threading.Lock()
        self.session_key = None
        self.account_id = None
        self.created = 0


SESSION = Session()

# >>> BAPATCH-MULTIACCT v1 BEGIN >>>   (work/ba/server/deploy/_build_multiacct)
# 多账号会话：一张卡一个 Shittim 存档。开关文件 cn_multiacct.txt
#   （bridge 目录 -> /www/wwwroot/bapatch/tools -> /www/wwwroot/bapatch；1/on/true/yes=开），
#   环境变量 CN_MULTIACCT 优先级更高。**文件不存在 / 内容不是真值 = 关 = 基线行为**。
#
# 三块（全部按 publisherId 分桶）：
#   ① enter_ticket(pub)   票据按账号派生 base64("pub/TOKEN")；pub 空/非数字/==UID -> 基线常量
#   ② acct_session(rec)   会话按账号分桶：dict + 每桶自己的 Session（含自己的 lock）
#   ③ acct_pub_for(rec)   路由按账号：请求片段里的 DevId -> account_service -> publisher_account_id
#
# 红线（开关关时逐字不动）：
#   * acct_session() 一律返回下面这个基线单例 SESSION（**同一个对象、同一把锁**），
#     所以 ensure_session / _rl_clear_session / 各生成器读到的与会话相关的值完全不变；
#   * acct_pub_for() 第一行就返回 None，不读开关文件之外的任何东西，也不往 rec 写任何字段。
CN_MULTIACCT_FILE = 'cn_multiacct.txt'
_SESS_BUCKETS = {}                      # str(publisher_id) -> Session（桶里字段与基线一致）
_SESS_BUCKETS_LOCK = threading.Lock()   # 只保护这个 dict：持锁期间只做字典操作，绝不做网络 IO

_CN_DEVID_RE = re.compile(r'"DevId"\s*:\s*"?([0-9]{4,24})"?')
_CN_DUID_RE = re.compile(r'"DeviceUniqueId"\s*:\s*"([^"]{6,128})"')
_CN_SID_RE = re.compile(r'"AccountServerId"\s*:\s*([0-9]{6,24})')


def cn_multiacct_on(base=None):
    """多账号会话开关。环境变量 CN_MULTIACCT 优先；否则读开关文件。缺失/读不到 -> False。"""
    try:
        env = (os.environ.get('CN_MULTIACCT') or '').strip().lower()
    except Exception:
        env = ''
    if env:
        return env in ('1', 'on', 'true', 'yes')
    try:
        _p, v = rl_read_file(CN_MULTIACCT_FILE, base)      # 复用 relay 的开关读取（同目录顺序）
    except Exception:
        return False
    if v is None:
        return False
    try:
        return v.strip().lower() in ('1', 'on', 'true', 'yes')
    except Exception:
        return False


def _cn_pub_key(pub):
    """publisherId -> 分桶 key（str）。空 / 非数字 / <=0 -> None（落回默认桶）。"""
    if pub is None:
        return None
    try:
        s = str(pub).strip()
    except Exception:
        return None
    if not s or not s.isdigit():
        return None
    try:
        return s if int(s) > 0 else None
    except Exception:
        return None


def enter_ticket(pub=None):
    """EnterTicket = base64("publisherId/TOKEN")；TOKEN 仍是基线那个常量。

    pub 为空 / 非数字 / 等于老账号 UID 时返回基线常量 ENTER_TICKET ——
    老玩家那张票逐字节不变（Shittim 侧仍是 ServerId=2），这是红线。
    """
    key = _cn_pub_key(pub)
    if not key or key == str(UID):
        return ENTER_TICKET
    try:
        return base64.b64encode(('%s/%s' % (key, TOKEN)).encode()).decode()
    except Exception:
        return ENTER_TICKET


def _acct_frag_text(rec=None, frag=None):
    """本请求的明文请求片段。优先用调用方传进来的 frag，其次 _FRAG_TLS（**只读，绝不消费**）。

    _FRAG_TLS 是 DevId 唯一能到达业务逻辑的通路（rec['req_DevId'] 在 devid_stash 里已脱敏），
    所以这里只读不清；真正消费它的是基线的 _req_dict，语义一点没动。
    再次是 rec 里本来就有、且基线自己也会写的两处明文片段（simple / p3 的路由自己存的）。
    """
    if isinstance(frag, str) and frag.strip():
        return frag
    try:
        if rec is not None and getattr(_FRAG_TLS, 'seq', None) == _req_seq(rec):   # [修 3] 不再比 id(rec)
            v = getattr(_FRAG_TLS, 'v', None)
            if isinstance(v, str) and v.strip():
                return v
    except Exception:
        pass
    if isinstance(rec, dict):
        for _k in ('simple_frag', 'p3_frag_head'):
            try:
                v = rec.get(_k)
            except Exception:
                v = None
            if isinstance(v, str) and v.strip():
                return v
    return ''


def _acct_dev_id_from_text(text):
    """片段 -> (dev_id, source)。口径与 account_service.identify 完全一致：
    有 DevId 用 DevId（纯数字串）；否则 DeviceUniqueId -> 'duid:<小写>'。"""
    if not isinstance(text, str) or not text:
        return None, 'none'
    m = _CN_DEVID_RE.search(text)
    if m:
        return m.group(1).strip(), 'devid'
    m = _CN_DUID_RE.search(text)
    if m:
        du = m.group(1).strip().lower()
        if du:
            return 'duid:' + du, 'duid'
    return None, 'none'


def _acct_pub_by_dev_id(dev_id, src):
    """dev_id -> account_service.get_account_by_dev_id(dev_id) -> publisher_account_id。

    只有一次 sqlite 查询（连接是 thread-local），没有网络 IO。失败/无行 -> (None, 原因)。
    """
    try:
        acct = _svc().get_account_by_dev_id(dev_id)
    except Exception as e:
        acct_fallback('multiacct get_account_by_dev_id: %r' % (e,))
        return None, 'err:devid'
    if acct is None:
        return None, src + ':no-row'
    try:
        pub = int(getattr(acct, 'publisher_account_id', 0) or 0)
    except Exception:
        pub = 0
    if pub <= 0:
        return None, src + ':no-pub'
    return pub, src


def _acct_pub_by_sid(text, src):
    """第二来源：同一份明文片段里的 SessionKey.AccountServerId（客户端回显的 accounts.server_id）。

    只在第一步拿不到 DevId 时用；同样只查本库、不用任何跨请求缓存。
    """
    m = _CN_SID_RE.search(text or '')
    if not m:
        return None, src
    try:
        sid = int(m.group(1))
    except Exception:
        return None, src
    if sid <= 0:
        return None, src
    try:
        acct = _svc().get_account(sid)
    except Exception as e:
        acct_fallback('multiacct get_account: %r' % (e,))
        return None, 'err:sid'
    if acct is None:
        return None, src + '+sid:no-row'
    try:
        pub = int(getattr(acct, 'publisher_account_id', 0) or 0)
    except Exception:
        pub = 0
    if pub <= 0:
        return None, src + '+sid:no-pub'
    return pub, 'sid'


def acct_pub_for(rec=None, frag=None):
    """本请求的 publisherId。**每请求只解析一次**（结果放在 rec 里，绝不跨请求缓存）。

    解析不到 / 任何异常 -> None，调用方据此落回基线行为（绝不让请求失败）。
    """
    try:
        if not cn_multiacct_on():
            return None
    except Exception:
        return None
    if isinstance(rec, dict) and 'acct_pub' in rec:
        return rec.get('acct_pub')                     # 本请求已解析过（含"解析不到"这种结论）
    pub = None
    src = 'none'
    try:
        text = _acct_frag_text(rec, frag)
        if text:
            dev_id, dsrc = _acct_dev_id_from_text(text)
            src = dsrc
            if dev_id:
                pub, src = _acct_pub_by_dev_id(dev_id, dsrc)
            if not pub:
                pub, src = _acct_pub_by_sid(text, src)
    except Exception as e:
        pub = None
        src = 'err:' + type(e).__name__
        try:
            acct_fallback('multiacct resolve: %r' % (e,))
        except Exception:
            pass
    try:
        pub = int(pub) if pub else None
    except Exception:
        pub = None
    if isinstance(rec, dict):
        try:
            rec['acct_pub'] = pub
            rec['acct_pub_src'] = src
        except Exception:
            pass
    return pub


def acct_session(rec=None, pub=None):
    """本请求该用哪个 Session 桶。

    开关关 / 解析不到 pub / pub == 老账号 UID -> 返回基线单例 SESSION（同一个对象、同一把锁）。
    否则返回该 publisher 自己的 Session：**桶里字段与基线一致，锁也是每桶一把**，
    所以两个账号的请求不会互相串行，也不会互相覆盖。
    """
    try:
        if not cn_multiacct_on():
            return SESSION
    except Exception:
        return SESSION
    try:
        p = acct_pub_for(rec) if pub is None else pub
        key = _cn_pub_key(p)
    except Exception:
        return SESSION
    if not key or key == str(UID):
        return SESSION
    try:
        b = _SESS_BUCKETS.get(key)
        if b is not None:
            return b
        with _SESS_BUCKETS_LOCK:                       # 只保护 dict：里面没有 IO / 没有 post_gateway
            b = _SESS_BUCKETS.get(key)
            if b is None:
                b = Session()
                _SESS_BUCKETS[key] = b
            return b
    except Exception:
        return SESSION


def _sid_writeback(pub, shittim_sid, rec=None):
    """[PATCH-PY-20261118-sidwb] 把新铸会话拿到的 Shittim ServerId 回写到本库。

    Shittim 的 Account_CheckNexon 回来了一个真账号 id（= Shittim 侧 Accounts.ServerId），
    以前只留在内存里的 sess.account_id，重启/换桶就丢。这里顺手记到
    accounts.shittim_server_id（由 account_service.set_shittim_server_id 落库）。

    旁路写：**任何失败只留痕，绝不影响登录**。
    结果写在 rec['acct_sid_wb']：
        'ok:<sid>'          写进去了
        'skip:noop:<sid>'   库里已经是这个值（幂等命中，没有产生 UPDATE）
        'skip:off'          多账号开关关（调用点就不该进来，防御性兜底）
        'skip:no-pub'       publisherId 无效
        'skip:legacy-uid'   老账号本人（那条链走基线单例，本来也不该进来）
        'skip:no-sid'       Shittim 没给出可用的整型 AccountServerId
        'skip:err:<类型>'   落库时抛了（已吞）
    """
    st = 'skip:unknown'
    try:
        try:
            _on = cn_multiacct_on()
        except Exception:
            _on = False
        key = _cn_pub_key(pub) if _on else None
        try:
            sid = int(shittim_sid or 0)
        except Exception:
            sid = 0
        if not _on:
            st = 'skip:off'
        elif not key:
            st = 'skip:no-pub'
        elif key == str(UID):
            st = 'skip:legacy-uid'
        elif sid <= 0:
            st = 'skip:no-sid'
        else:
            wrote = _svc().set_shittim_server_id(int(key), sid)
            st = ('ok:%d' % sid) if wrote else ('skip:noop:%d' % sid)
    except Exception as e:
        st = 'skip:err:' + type(e).__name__
        try:
            acct_fallback('sid writeback pub=%r sid=%r: %r' % (pub, shittim_sid, e))
        except Exception:
            pass
    try:
        if isinstance(rec, dict):
            rec['acct_sid_wb'] = st
    except Exception:
        pass
    return st
# <<< BAPATCH-MULTIACCT v1 END <<<

# >>> BAPATCH-SESSTTL v1 BEGIN >>>   (work/ba/server/deploy/_build_ttl)
# 会话 TTL：桥的会话缓存以前**永不过期**（线上实测最近 300 条 cache 299 / fresh 1），
# 于是 Shittim 的封禁守卫（AccountHandler.cs:104-112，State==Dormant 抛 ACCOUNT_SUSPENDED）
# 虽然写在 Account_CheckNexon(1014) 里，却被"命中缓存就直接 return"整条短路 —— 封了也照进。
#
# 开关文件：/www/wwwroot/bapatch/cn_session_ttl.txt
#   （bridge 目录 -> /www/wwwroot/bapatch/tools -> /www/wwwroot/bapatch，
#     与 cn_multiacct.txt 同一套查找顺序），内容 = 秒数整数；
#   环境变量 CN_SESSION_TTL 优先级更高；**文件缺失 / 内容不是整数 -> 120**。
#   >0   会话年龄超过这么多秒 = 过期：清该桶 -> 重新铸会话（真打 1014）
#   <=0  关闭 TTL（保持旧的永不过期行为；紧急回退用）
# 只影响 ensure_session 的"缓存命中"判定：票据派生 / 分桶 / _sid_writeback / _FRAG_TLS /
# AES / UNIQUE(dev_id) 一律不动。
CN_SESSION_TTL_FILE = 'cn_session_ttl.txt'
CN_SESSION_TTL_DEFAULT = 120


def cn_session_ttl(base=None):
    """会话 TTL 秒数。环境变量 CN_SESSION_TTL 优先，否则读开关文件；解析失败 -> 默认 120。

    <=0 = 关闭 TTL（旧行为）。任何异常都只回落默认值，绝不抛（登录链路上不允许炸）。
    """
    v = None
    try:
        v = os.environ.get('CN_SESSION_TTL')
    except Exception:
        v = None
    if v is None or not str(v).strip():
        try:
            _p, v = rl_read_file(CN_SESSION_TTL_FILE, base)    # 复用 relay 的开关读取（同目录顺序）
        except Exception:
            v = None
    try:
        return int(str(v).strip())
    except Exception:
        return CN_SESSION_TTL_DEFAULT


# <<< BAPATCH-SESSTTL v1 END <<<

# >>> BAPATCH-BANEXP v1 BEGIN >>>   (work/ba/server/deploy/_build_banexp)
# 「限时账号封禁」的到期自动解封 —— 桥里只做这一件事，**不拦人、不改任何协议**。
#
# 背景：Shittim 的 Accounts.State=2(Dormant) 是"永久位"，它不会自己过期；
#       面板给限时账号封禁写 State=2 只是为了让"封得住"这件事不依赖封禁表，
#       到期后必须有人把它改回 1。桥是唯一一个"每次账号鉴权都会跑、而且知道这是哪个账号"的地方，
#       所以在这里做**读取侧自愈**：
#         bans(kind='account', target=<publisherId>) 命中且 until_epoch <= now
#           -> POST /api/admin/account/update {ServerId, State:1}
#           -> 成功后删掉那一行（下次不再重复；失败就留着，下次鉴权再试）
#
# 硬约束：全部 try/except；读不到库 / 没有 admin key / 算不出 serverId / HTTP 失败
#         -> 一律**放行**（绝不因为封禁表出问题就把人拦在门外）。
#         本块不碰 TTL / 多账号分桶 / 票据派生：只在 ensure_session 最前面加一次调用。
BANEXP_DB = os.environ.get('BA_BANS_DB') or ACCT_DB
BANEXP_TIMEOUT = float(os.environ.get('BA_BANEXP_HTTP_TIMEOUT') or 3.0)


def banexp_on():
    """紧急开关：环境变量 BA_BANEXP=0/off/false/no 时整段自愈直接关掉。"""
    try:
        v = os.environ.get('BA_BANEXP')
        if v is not None and str(v).strip().lower() in ('0', 'off', 'false', 'no'):
            return False
    except Exception:
        pass
    return True


def _banexp_ro_uri(path):
    """绝对路径 -> SQLite 只读 URI（Windows 的盘符路径要变成 file:/C:/... 才认）。"""
    import urllib.parse as _up
    p = os.path.abspath(str(path)).replace('\\', '/')
    if not p.startswith('/'):
        p = '/' + p
    return 'file:' + _up.quote(p, safe='/:') + '?mode=ro'


def _banexp_connect(ro=True):
    """打开桥接库。ro=True 用 SQLite 只读 URI（不可能写坏别人的库）。"""
    import sqlite3
    if ro:
        return sqlite3.connect(_banexp_ro_uri(BANEXP_DB), uri=True, timeout=1.0)
    return sqlite3.connect(str(BANEXP_DB), timeout=5.0)


def banexp_account_row(pub):
    """bans 表里该 publisher 的账号封禁行 -> dict | None。任何异常 -> None（= 没封禁）。"""
    try:
        p = int(pub or 0)
        if p <= 0:
            return None
        row = None
        conn = _banexp_connect(True)
        try:
            cur = conn.execute(
                "SELECT kind, target, until_epoch, reason, created_at FROM bans"
                " WHERE kind = 'account' AND target = ? LIMIT 1", (str(p),))
            row = cur.fetchone()
        finally:
            try:
                conn.close()
            except Exception:
                pass
        if not row:
            return None
        return {'kind': row[0], 'target': row[1], 'until_epoch': row[2],
                'reason': row[3], 'created_at': row[4]}
    except Exception:
        return None


def _banexp_delete_account_row(pub):
    """删掉那一行（自愈成功后调用）。失败返回 0，不抛。"""
    try:
        p = int(pub or 0)
        if p <= 0:
            return 0
        conn = _banexp_connect(False)
        try:
            cur = conn.execute("DELETE FROM bans WHERE kind = 'account' AND target = ?", (str(p),))
            conn.commit()
            n = cur.rowcount
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return int(n or 0)
    except Exception:
        return 0


def _banexp_resolve_sid(pub):
    """publisherId -> Shittim AccountServerId（先用 account_service 的 admin 列表，再退回本库回写列）。"""
    try:
        import account_service as _as
    except Exception:
        _as = None
    sid = 0
    if _as is not None:
        try:
            accounts = _as.sid_list_accounts(1.5)
            sid = int(_as.sid_lookup(accounts, int(pub)) or 0)
        except Exception:
            sid = 0
    if sid > 0:
        return sid
    try:
        conn = _banexp_connect(True)
        try:
            cur = conn.execute(
                'SELECT shittim_server_id FROM accounts WHERE publisher_account_id = ? LIMIT 1',
                (int(pub),))
            row = cur.fetchone()
        finally:
            try:
                conn.close()
            except Exception:
                pass
        if row and row[0]:
            return int(row[0])
    except Exception:
        pass
    return 0


def _banexp_admin_update(server_id, state, timeout=None):
    """POST /api/admin/account/update {ServerId, State}。成功返回 True，任何异常 False。"""
    try:
        import account_service as _as
    except Exception:
        return False
    try:
        key = ''
        fn = getattr(_as, '_resolve_admin_key', None)
        if callable(fn):
            key = str(fn() or '')
        if not key:
            return False
        base = str(getattr(_as, '_ADMIN_URL', '') or 'http://127.0.0.1:5000').rstrip('/')
        payload = json.dumps({'ServerId': int(server_id), 'State': int(state)}).encode('utf-8')
        req = urllib.request.Request(
            base + '/api/admin/account/update', data=payload,
            headers={'X-Admin-Key': key, 'Content-Type': 'application/json',
                     'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=(timeout or BANEXP_TIMEOUT)) as r:
            code = int(getattr(r, 'status', 200) or 200)
            try:
                r.read()
            except Exception:
                pass
        return 200 <= code < 300
    except Exception:
        return False


def banexp_release_account(pub, rec=None):
    """到期自愈主流程。返回 'none'|'active'|'released'|'release-failed'|'error'，绝不抛。"""
    try:
        p = int(pub or 0)
    except Exception:
        return 'error'
    if p <= 0:
        return 'none'
    row = banexp_account_row(p)
    if row is None:
        return 'none'
    until = row.get('until_epoch')
    try:
        if until is not None and int(until) > int(time.time()):
            if isinstance(rec, dict):
                rec['banexp_account'] = 'active'
            return 'active'
        if until is None:
            if isinstance(rec, dict):
                rec['banexp_account'] = 'permanent'
            return 'active'
    except Exception:
        return 'error'
    sid = _banexp_resolve_sid(p)
    if sid <= 0:
        if isinstance(rec, dict):
            rec['banexp_account'] = 'expired:no-sid'
        acct_log('[banexp] expired account ban pub=%s, but no shittim server_id' % p)
        return 'release-failed'
    if not _banexp_admin_update(sid, 1):
        if isinstance(rec, dict):
            rec['banexp_account'] = 'expired:update-failed'
        acct_log('[banexp] release State=1 failed sid=%s pub=%s' % (sid, p))
        return 'release-failed'
    deleted = _banexp_delete_account_row(p)
    if isinstance(rec, dict):
        rec['banexp_account'] = 'released'
        rec['banexp_released_sid'] = sid
    acct_log('[banexp] expired account ban released sid=%s pub=%s until=%s deleted_rows=%s'
             % (sid, p, until, deleted))
    return 'released'


def banexp_gate(rec, pub=None):
    """ensure_session 最前面调一次；任何异常都吞掉（放行）。"""
    try:
        if not banexp_on():
            return
        p = pub
        if p is None:
            try:
                p = acct_pub_for(rec)
            except Exception:
                p = None
        try:
            p = int(p or 0)
        except Exception:
            p = 0
        if p <= 0:
            return
        banexp_release_account(p, rec)
    except Exception:
        pass
# <<< BAPATCH-BANEXP v1 END <<<

# >>> BAPATCH-BANREPLY v1 BEGIN >>>   (work/ba/server/deploy/_build_banreply)
# 桥侧封禁拦截：命中 bans 表就回**官方原生**的 AccountBanErrorPacket。
#
#     Protocol  = Protocol.Error = -1       （ProtocolData.cs:19 `Error = -1`；包内 getter NetworkProtocol.cs:784）
#     ErrorCode = 1025 AccountLoginError    （ProtocolData.cs:720；包内是常量 getter NetworkProtocol.cs:807）
#     BanReason = <自由字符串>              （NetworkProtocol.cs:808；包内**唯一**数据字段）
#
# 客户端弹的是它自己的本地文案（官方 Excel LocalizeErrorDB 行 167），桥只负责填空：
#     账号已被禁止使用，
#     如有任何问题请咨询客服！
#     封禁周期至：<BanReason>
# ⇒ **零改客户端**：不碰 dex / res / AXML / ExcelDB / SDK。
#
# 开关：cn_banreply.txt（目录查找顺序与 cn_multiacct.txt / cn_session_ttl.txt 完全一致），
#       内容 1/on/true/yes = 开；环境变量 CN_BANREPLY 优先；
#       **文件不存在 / 读不到 / 内容不是真值 = 关 = 与基线逐字一致**（开关判定在协议名白名单之后，
#       非登录协议连文件都不读，热路径只多一次 frozenset 查找）。
# 拦截点：_bridge 里 name 一确定（name_fix_resolve 之后、billing/dedup 之前）就判，只对登录握手协议生效：
#       Account_CheckNexon(1014) / Account_Auth(1002) / Account_Auth2(1012)。
#       CN_BANREPLY_ALL=1 时对所有协议都拦（调试 / 踢在线用）。
#
# 红线：① 只读 bans 表（sqlite 只读 URI，复用 banexp_account_row）；
#       ② 任何异常一律"放行"（绝不因为查封禁表失败把人拦在门外）；
#       ③ 不碰 TTL / 多账号分桶 / 票据派生 / _FRAG_TLS / AES / UNIQUE(dev_id)；
#       ④ 解析 publisher 时写的是 rec 的**浅拷贝**，绝不污染 rec['acct_pub'] 的既有缓存语义。
CN_BANREPLY_FILE = 'cn_banreply.txt'
# >>> 2026-11-18 真机定案：客户端认的是 WebAPIErrorCode.AccountBanned = 27000，不是 1025 >>>
#   1025 (AccountLoginError) 只是**服务端 DTO** AccountBanErrorPacket.get_ErrorCode 的常量，
#   客户端本地化表 LocalizeErrorDBSchema 里没有这一行 ⇒ 只会回落到阶段兜底文案
#   「同步资源信息时失败。将返回标题画面。」（真机实测，21:04 / 21:09）。
#   证据链：
#     work\ba\data\ExcelDB.db -> LocalizeErrorDBSchema（按枚举顺序存放）
#       row167「无法找到保存信息。」   = ContentSaveDBNotFound = 26000
#       row168「账号已被禁止使用，⏎如有任何问题请咨询客服！⏎封禁周期至：」= AccountBanned = 27000
#       row169+ 正好是 28000 ServerNowLoadingProhibitedWord 起的 6 个成员
#     Schale\MX\NetworkProtocol\ProtocolData.cs:979  AccountBanned = 27000
#     真机：ErrorCode=3(InvalidSession) -> 弹「无效的会话。」（证明通道正常）
#           ErrorCode=27000            -> 弹官方封禁窗（21:29 成功）
CN_BANREPLY_CODE = 27000                     # WebAPIErrorCode.AccountBanned
CN_BANREPLY_CODE_LEGACY = 1025               # 仅留档：已经证伪，别再用
CN_BANREPLY_PERMANENT = '永久'
CN_BANREPLY_TZ_HOURS = 8                     # ban_message.py 同款：Asia/Shanghai 写死 UTC+8（不依赖 tzdata）
CN_BANREPLY_TIME_FMT = '%Y-%m-%d %H:%M'      # ban_message.py:TIME_FMT 同款（分钟精度，秒截断）
CN_BANREPLY_MAX_CHARS = 40                   # 弹窗 4 行的经验上限（OFFICIAL_BAN_UI_STUDY.md §5）
CN_BANREPLY_PROTO = frozenset(('Account_CheckNexon', 'Account_Auth', 'Account_Auth2'))
_CN_BANREPLY_TICKET_RE = re.compile(r'"EnterTicket"\s*:\s*"([A-Za-z0-9+/=]{8,})"')

# >>> BANPROBE v1 BEGIN >>>  （真机 A/B 探测：只在开关文件存在时改变行为，缺失=原样）
CN_BANREPLY_CODE_FILE = 'cn_banreply_code.txt'    # 覆盖 ErrorCode（整数）。默认 1025
CN_BANREPLY_SHAPE_FILE = 'cn_banreply_shape.txt'  # 覆盖封禁包形状（见 banreply_shape）
CN_BANREPLY_HEAT_FILE = 'cn_banreply_heat.txt'    # 覆盖"第几次命中"的行为，用于一次开机试多个变体


def banreply_code_override(base=None):
    """cn_banreply_code.txt -> 覆盖 ErrorCode。缺失/异常 -> CN_BANREPLY_CODE（行为不变）。"""
    try:
        _p, v = rl_read_file(CN_BANREPLY_CODE_FILE, base)
        if v:
            _n = int(str(v).strip().split()[0])
            if -1000000 < _n < 1000000:
                return _n
    except Exception:
        pass
    return CN_BANREPLY_CODE


def banreply_shape(base=None):
    """cn_banreply_shape.txt -> 封禁包形状。缺失/其它 -> ''（=现状：官方 AccountBanErrorPacket）。

    'err'  内层只留 {Protocol, ServerTimeTicks, ErrorCode}，**不发 BanReason**
           —— 用来区分"客户端不认 -1"与"客户端不认 1025"
    'auth' 内层 Protocol 用 1002，外层 protocol 用 'Account_Auth'
           —— 用来验证 ProtocolConverter 只认正数协议号
    'forbid' 纯 ErrorPacket（同 'err'）但外层 protocol 仍是 'Error'
    """
    try:
        _p, v = rl_read_file(CN_BANREPLY_SHAPE_FILE, base)
        return (v or '').strip().lower()
    except Exception:
        return ''


def _banreply_probe_seq(rec):
    """命中序号（进程内单调递增，跨请求；rec 里的值只作记录）。"""
    try:
        if isinstance(rec, dict):
            n = rec.get('_banprobe_seq')
            if isinstance(n, int) and n > 0:
                return n
    except Exception:
        pass
    return 0


_BANPROBE_N = [0]


def _banreply_probe_next(rec):
    """把全局计数器 +1 并回写 rec，返回本次命中序号（1 起）。"""
    _BANPROBE_N[0] += 1
    n = _BANPROBE_N[0]
    try:
        if isinstance(rec, dict):
            rec['_banprobe_seq'] = n
    except Exception:
        pass
    return n


def banreply_heat_plan(rec):
    """cn_banreply_heat.txt 内容形如 `1:errcode=1025;2:shape=err;3:shape=auth`
    -> 返回 ('ban'|'err'|'auth', code) 表示本次命中该发什么；文件缺失 -> None。"""
    try:
        _p, v = rl_read_file(CN_BANREPLY_HEAT_FILE)
        if not v:
            return None
        seq = _banreply_probe_next(rec)
        plan = None
        for item in str(v).replace('\n', ';').split(';'):
            item = item.strip()
            if not item or ':' not in item:
                continue
            left, right = item.split(':', 1)
            try:
                idx = int(left.strip())
            except Exception:
                continue
            if idx == seq:
                plan = right.strip()
                break
        if plan is None:
            return ('ban', CN_BANREPLY_CODE)
        code = CN_BANREPLY_CODE
        shape = 'ban'
        for kv in plan.split(','):
            kv = kv.strip()
            if '=' not in kv:
                continue
            k, val = kv.split('=', 1)
            k = k.strip().lower()
            if k in ('errcode', 'code'):
                try:
                    code = int(val.strip())
                except Exception:
                    pass
            elif k == 'shape':
                shape = val.strip().lower()
        return (shape, code)
    except Exception:
        return None
# <<< BANPROBE v1 END <<<


def banreply_on(base=None):
    """封禁拦截开关。环境变量 CN_BANREPLY 优先，否则读开关文件；缺失/异常 -> False。"""
    try:
        env = (os.environ.get('CN_BANREPLY') or '').strip().lower()
    except Exception:
        env = ''
    if env:
        return env in ('1', 'on', 'true', 'yes')
    try:
        _p, v = rl_read_file(CN_BANREPLY_FILE, base)     # 复用 relay 的开关读取（同目录顺序）
    except Exception:
        return False
    if v is None:
        return False
    try:
        return v.strip().lower() in ('1', 'on', 'true', 'yes')
    except Exception:
        return False


def banreply_all():
    """CN_BANREPLY_ALL=1 -> 所有协议都判（默认只判登录握手三个协议）。"""
    try:
        return (os.environ.get('CN_BANREPLY_ALL') or '').strip().lower() in ('1', 'on', 'true', 'yes')
    except Exception:
        return False


def _banreply_fmt_time(epoch):
    """epoch 秒 -> 'YYYY-MM-DD HH:MM'（UTC+8 写死、秒截断）。绝不抛。"""
    try:
        import datetime as _d
        dt = _d.datetime.fromtimestamp(int(epoch),
                                       _d.timezone(_d.timedelta(hours=CN_BANREPLY_TZ_HOURS)))
        return dt.strftime(CN_BANREPLY_TIME_FMT)
    except Exception:
        return ''


def _banreply_parse_created(value):
    """bans.created_at -> epoch 秒。口径与 ban_message.py:parse_created 逐条一致；认不出 -> None。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except Exception:
            return None
    try:
        s = str(value).strip()
    except Exception:
        return None
    if s == '':
        return None
    if s.isdigit():
        try:
            return int(s)
        except Exception:
            return None
    s2 = s.replace('T', ' ')
    if s2.endswith('Z'):
        s2 = s2[:-1].strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S.%f'):
        try:
            import datetime as _d
            dt = _d.datetime.strptime(s2, fmt).replace(
                tzinfo=_d.timezone(_d.timedelta(hours=CN_BANREPLY_TZ_HOURS)))
            return int(dt.timestamp())
        except Exception:
            continue
    return None


def _banreply_ticks():
    """ServerTimeTicks：.NET ticks（0001-01-01 起 100ns），**秒精度**（同 ResponsePacket.TruncateToSeconds）。"""
    try:
        import datetime as _d
        now = _d.datetime.now()
        return int((now - _d.datetime(1, 1, 1)).total_seconds()) * 10000000
    except Exception:
        return 0


def banreply_reason(until_epoch, start_epoch=None):
    """BanReason 文案。**只产出 "X 至 Y" 这一段 / 或 "永久"**。

    与 ban_message.py 的差异（同格式串、同时区、同退化规则，但去掉两头）：
        ban_message.py:ban_message()  ->  '封号时间 X 至 Y，请联系客服'  /  '封禁，请联系客服'
        这里 BanReason                ->  'X 至 Y'                      /  '永久'
    前缀 '账号已被禁止使用，\\n如有任何问题请咨询客服！\\n封禁周期至：' 由客户端本地文案自带。
    绝不抛。
    """
    try:
        if until_epoch is None or isinstance(until_epoch, bool):
            return CN_BANREPLY_PERMANENT
        if isinstance(until_epoch, str) and until_epoch.strip() == '':
            return CN_BANREPLY_PERMANENT
        end = _banreply_fmt_time(until_epoch)
        if end == '':
            return CN_BANREPLY_PERMANENT
        beg = _banreply_fmt_time(start_epoch) if start_epoch is not None else ''
        if beg == '':
            beg = end                     # 起点缺失 -> 起点=终点（与 ban_message.py 同一条退化规则）
        return '%s 至 %s' % (beg, end)
    except Exception:
        return CN_BANREPLY_PERMANENT


def banreply_row_for(pub, now=None):
    """该 publisher 是否处于**封禁中** -> bans 行 dict；否则 None。只读、绝不抛。

    读侧语义与 bans 表约定完全一致（schema.sql:15-18）：
        until_epoch IS NULL                      -> 永久封禁
        until_epoch IS NOT NULL AND <= now        -> 已到期 = 不封禁（边界：== now 算过期）
        until_epoch IS NOT NULL AND  > now        -> 限时封禁中
    """
    try:
        p = int(pub or 0)
    except Exception:
        return None
    if p <= 0:
        return None
    try:
        row = banexp_account_row(p)           # [BAPATCH-BANEXP v1] 同一个只读 SELECT（任何异常 -> None）
    except Exception:
        return None
    if not row:
        return None
    try:
        until = row.get('until_epoch')
        if until is None or isinstance(until, bool):
            return row                        # 永久
        if isinstance(until, str) and until.strip() == '':
            return row                        # 永久
        try:
            u = int(until)
        except Exception:
            return row                        # 解析不了 -> 按永久（与 ban_message.is_permanent 一致）
        cur = int(time.time()) if now is None else int(now)
        return row if u > cur else None
    except Exception:
        return None


def banreply_pub_from_ticket(frag):
    """客户端 1014 请求里的 EnterTicket = base64("publisherId/TOKEN") -> publisherId。

    这与**官方服务端自己**取身份的写法完全一致（AccountHandler.cs:58-63 就是解这个串切 parts[0]）。
    只在 acct_pub_for() 给不出 publisher 时才用；解析不出 -> None。
    """
    try:
        if not isinstance(frag, str) or not frag:
            return None
        m = _CN_BANREPLY_TICKET_RE.search(frag)
        if not m:
            return None
        s = m.group(1)
        raw = base64.b64decode(s + '=' * ((4 - len(s) % 4) % 4))
        head = raw.decode('utf-8', 'replace').split('/', 1)[0].strip()
        if not head.isdigit():
            return None
        p = int(head)
        return p if p > 0 else None
    except Exception:
        return None


def banreply_resolve_pub(rec=None, frag=None):
    """本请求的 publisherId（**不污染 rec['acct_pub']**）。绝不抛。

    1) rec 里已被基线解析过 -> 直接用（沿用"每请求只解析一次"的既有约定）
    2) 复用 acct_pub_for()：DevId -> account_service，或 SessionKey.AccountServerId -> accounts 行
       （写进的是浅拷贝 probe，真 rec 一个字段都不动 —— 否则会毒化 ensure_session 的分桶结果）
    3) acct_pub_for() 是**受 cn_multiacct 开关约束**的（关着它第一行就 return None）。
       那种情况下用同一个库的 _acct_pub_by_sid() 再试一次 SessionKey.AccountServerId。
       开关开着时 acct_pub_for 已经试过 sid，这里就跳过，不多查一次库。
    4) EnterTicket 里的 publisherId（官方服务端同一来源，AccountHandler.cs:58-63）
    """
    try:
        if isinstance(rec, dict) and 'acct_pub' in rec:
            try:
                p0 = int(rec.get('acct_pub') or 0)
            except Exception:
                p0 = 0
            if p0 > 0:
                return p0
    except Exception:
        pass
    pub = None
    try:
        probe = dict(rec) if isinstance(rec, dict) else {}
        probe.pop('acct_pub', None)
        probe.pop('acct_pub_src', None)
        pub = acct_pub_for(probe, frag)
    except Exception:
        pub = None
    if not pub:
        try:
            _mc = cn_multiacct_on()
        except Exception:
            _mc = False
        if not _mc:
            try:
                pub, _src = _acct_pub_by_sid(frag or '', 'banreply')
            except Exception:
                pub = None
    if not pub:
        pub = banreply_pub_from_ticket(frag)
    try:
        p = int(pub or 0)
    except Exception:
        p = 0
    return p if p > 0 else None


def banreply_build(rec=None, frag=None, now=None):
    """-> (pub, inner)。inner 是官方 AccountBanErrorPacket 的**内层 JSON**；不拦 -> (None, None)。

    inner 形状与 Shittim 网关序列化出来的一致（jsonSettings：NullValueHandling.Ignore +
    DefaultValueHandling.Ignore，基类成员在前；Protocol=-1 不是默认值 0，所以它**会**上线）：
        {"Protocol":-1,"ServerTimeTicks":<ticks>,"ErrorCode":1025,"BanReason":"..."}
    """
    try:
        pub = banreply_resolve_pub(rec, frag)
        if not pub:
            return None, None
        row = banreply_row_for(pub, now)
        if not row:
            return None, None
        reason = banreply_reason(row.get('until_epoch'),
                                 _banreply_parse_created(row.get('created_at')))
        # >>> BANPROBE v1 BEGIN >>>  缺失所有探测开关时行为与改造前完全一致
        code = banreply_code_override()
        shape = banreply_shape()
        try:
            _plan = banreply_heat_plan(rec)
        except Exception:
            _plan = None
        if _plan:
            shape, code = _plan
        if isinstance(rec, dict):
            rec['banreply_code'] = code
            rec['banreply_shape'] = shape or 'ban'
        proto = 1002 if shape == 'auth' else -1
        inner = {'Protocol': proto,
                 'ServerTimeTicks': _banreply_ticks(),
                 'ErrorCode': code}
        if shape not in ('err', 'forbid'):
            inner['BanReason'] = reason
        # 2026-11-18 21:29 真机：ErrorCode=27000 + BanReason 就能让「封禁周期至：」后面出日期串，
        # 所以**不要再加 Reason**（多挂一个同值字段有被拼两遍的风险）。此处保持与 fa0d95b0 一致。
        # <<< BANPROBE v1 END <<<
        return pub, inner
    except Exception:
        return None, None


def banreply_response(handler, rec, name, packet_b64='', proto_str='', now=None):
    """命中 -> 可直接 return 的 (code, body, ctype)；未命中 -> None。**绝不抛**。

    信封走的是桥自己现成的两条出口（与 path B 的 Account_Auth 完全同一条）：
        cn_resp_format() == 'cn_envelope' -> _cn_envelope('Error', inner, rec)   （CN wire：cn_wire/cn_cipher）
        否则                              -> _json_ok('Error', inner)            （Shittim 形：protocol+packet 字串）
    两条的**外层 protocol 都是字符串 "Error"**，与官方 CreateProtocolErrorResponse
    （GatewayController.cs:781 `Protocol.Error.ToString()`）以及实测 CN 抓包
    （cn_wire.py:222 断言真实抓包 outer.protocol == 'Error'）一致。
    """
    try:
        if name not in CN_BANREPLY_PROTO and not banreply_all():
            return None                      # 热路径：一次 frozenset 查找，之后不读任何文件
        if not banreply_on():
            return None
        frag = ''
        try:
            frag = _acct_frag_text(rec)
        except Exception:
            frag = ''
        if not frag and packet_b64 and handler is not None:
            try:
                frag = handler._cn_decode_any(packet_b64, proto_str)   # 只读解密，异常已在内部吞掉
            except Exception:
                frag = ''
        pub, inner = banreply_build(rec, frag, now)
        if not inner:
            return None
        try:
            if isinstance(rec, dict):
                rec['banreply'] = 'hit'
                rec['banreply_pub'] = pub
                rec['banreply_reason'] = inner.get('BanReason')
                rec['banreply_reason_len'] = len(inner.get('BanReason') or '')
                if len(inner.get('BanReason') or '') > CN_BANREPLY_MAX_CHARS:
                    rec['banreply_reason_long'] = True
            acct_log('[banreply] AccountBanErrorPacket pub=%s code=%d reason=%r'
                     % (pub, CN_BANREPLY_CODE, inner.get('BanReason')))
        except Exception:
            pass
        if cn_resp_format() == 'cn_envelope':
            # >>> BANREPLY2 FIX-A BEGIN >>>
            # 封禁包必须"我给什么就编什么"地出去，**绝不能**再过 _cn_envelope：
            #   _cn_envelope:2815 -> _cn_enc_b64:3021，当 cn_wrap_mode in ('a_proto_int',
            #   'b_proto_str') 时那一支**完全忽略入参 inner_obj / proto_name**：
            #     :3023  inner = cn_inner27.build(1002)      <- 封禁 inner 在这里被丢掉
            #     :3026  wrap_response('Account_Auth', …)     <- 外层协议名也被硬写成 Account_Auth
            #   线上 resp_len=3500（= 重建出来的 Account_Auth）就是这么来的。
            #   _cn_send_envelope:3002 的契约正好相反（:3003 "Encode exactly the object we were
            #   given (no cn_wrap_mode re-building)"，:3006 直接 wrap_response(proto_name, obj)），
            #   且 1017 / 24000 / 1005 / CallName / Nickname 都在用它，线上已验证能通。
            #   只换调用点：cn_inner27.build / _cn_enc_b64 本体一字不动（别的协议还在用）。
            try:
                # >>> BANPROBE v1 >>>
                # shape='auth' 时外层协议名也用 'Account_Auth'（模拟"正常回包 + 错误码"），
                # 其余一律 'Error'（官方 CreateProtocolErrorResponse 的行为）。
                _out_name = 'Account_Auth' if (isinstance(rec, dict) and rec.get('banreply_shape') == 'auth') else 'Error'
                _br_out = handler._cn_send_envelope(_out_name, inner, rec)
            except Exception as _be:
                # 编码失败就放行（红线）：让 _bridge 继续走正常登录路径
                try:
                    if isinstance(rec, dict):
                        rec['banreply_err'] = repr(_be)
                except Exception:
                    pass
                acct_log('[banreply] _cn_send_envelope failed, fall through: %r' % (_be,))
                return None
            try:
                if isinstance(rec, dict):
                    rec['banreply_served'] = True          # 出口断言：封禁包确实按 Error 发出了
                    rec['banreply_out'] = 'cn_send_envelope'
            except Exception:
                pass
            return _br_out
            # <<< BANREPLY2 FIX-A END <<<
        return handler._json_ok('Error', inner)
    except Exception as e:
        try:
            if isinstance(rec, dict):
                rec['banreply_err'] = repr(e)
            acct_log('[banreply] error, fall through: %r' % (e,))
        except Exception:
            pass
        return None                               # 出错就放行（红线）
# <<< BAPATCH-BANREPLY v1 END <<<

# ==== BEGIN 24000_v3 (managed block) ====
# ==========================================================================
# 24000_v3 managed block -- DO NOT EDIT BY HAND
# 由 work/ba/server/deploy/patch_24000_v3.py 生成
# 基线 = _baseline/account_auth_probe.py  54026 B  sha256 f94b4fa05d95d4c8719f5623322b75629b81eed59442370dd552db721437dbc9
# 24000_v3 meta: engine=2.0.0 sha256=017c4624a75c7cd94000ecfcf07a62888853a8cfc577cba47338a668f6b71653
# 结构权威 = work/ba/proto/official_spec.json protocols["24000"]（7 键 / 71 zone / ZoneScheduleGroupRecords={} / RequestId==外层 requestid）
# 撤销：python3 patch_24000_v3.py --target <file> --rollback
# ==========================================================================
# ==== BEGIN ENGINE CORE (24000 v2) ====
B24000_PROTO = 24000
B24000_ENGINE_VERSION = '2.0.0'
B24000_TOP_KEYS = ('Protocol', 'SessionKey', 'ServerTimeTicks', 'ServerNotification',
                   'RequestId', 'AcademyDB', 'AcademyLocationDBs')

# AcademyZoneDBSchema.f1 的分组：location -> 该 location 的 zone id（ExcelDB 只读推导）
# 国服启用 9 个 location（AcademyLocationDBSchema 11 行去掉 14 Trinity / 18 Shanhaijing）
# zone 个数 8 + 7 + 8*7 = 71，与官方 24000 的 71 个键集合完全相等
B24000_ZONE_LAYOUT = (
    (1, (1, 10, 11, 12, 13, 14, 15, 16)),
    (7, (20, 21, 22, 23, 24, 25, 26)),
    (11, (30, 31, 32, 33, 34, 35, 36, 37)),
    (12, (40, 41, 42, 43, 44, 45, 46, 47)),
    (13, (50, 51, 52, 53, 54, 55, 56, 57)),
    (15, (70, 71, 72, 73, 74, 75, 76, 77)),
    (16, (80, 81, 82, 83, 84, 85, 86, 87)),
    (17, (90, 91, 92, 93, 94, 95, 96, 97)),
    (19, (110, 111, 112, 113, 114, 115, 116, 117)),
)
B24000_ENABLED_LOCATIONS = tuple(loc for loc, _zs in B24000_ZONE_LAYOUT)
B24000_ZONE_BY_LOCATION = dict(B24000_ZONE_LAYOUT)
B24000_ZONE_IDS = tuple(sorted(z for _loc, zs in B24000_ZONE_LAYOUT for z in zs))
# 键序 = 字典序（Go encoding/json 对 map 的序列化顺序），官方抓包实测如此
B24000_ZONE_KEY_ORDER = tuple(sorted(str(z) for z in B24000_ZONE_IDS))

# 新号学院地点：initial_state_rules.q8.initial.suggested_minimum
#   [{"LocationId": 1, "Rank": 1, "Exp": 0}]  （Rank 初值 high 置信；条数未找到规则）
B24000_DEFAULT_LOCATIONS = ({'LocationId': 1, 'Rank': 1, 'Exp': 0},)
# 官方那个 32 级号是 9 条（Rank 2/1/1/2/1/1/2/2/2，Exp 只有 19 号是 200）。
# 新号若上机因学院崩，改用它做 A/B：坐标全 1、Exp 全 0。
B24000_ALL9_LOCATIONS = tuple({'LocationId': loc, 'Rank': 1, 'Exp': 0}
                              for loc in B24000_ENABLED_LOCATIONS)


def b24000_ticks(dt=None):
    """.NET DateTime.Ticks：100ns 自 0001-01-01。整数运算，不经 float。

    口径证据：官方抓包 24000 的 ServerTimeTicks=639304002548158993 换算成
    2026-11-16T04:30:54.815899，与同一份抓包 meta 的墙钟 04:30:54.980 对齐
    => 单位确实是 100ns，且取的是**服务器本地墙钟**（不是 UTC）。
    """
    from datetime import datetime as _dt, timedelta as _td
    dt = dt or _dt.now()
    return ((dt - _dt(1, 1, 1)) // _td(microseconds=1)) * 10


def b24000_time_from_ticks(ticks):
    """ticks -> 同一个墙钟坐标系下的 datetime（与 b24000_ticks 互逆）。"""
    from datetime import datetime as _dt, timedelta as _td
    return _dt(1, 1, 1) + _td(microseconds=int(ticks) // 10)


def b24000_fmt_time(dt, frac=3):
    """'2026-11-16T04:00:06.479' —— 无时区、毫秒精度、尾零裁掉（官方 LastUpdate 形态）。"""
    s = '%04d-%02d-%02dT%02d:%02d:%02d' % (dt.year, dt.month, dt.day,
                                          dt.hour, dt.minute, dt.second)
    if frac:
        digits = ('%09d' % (dt.microsecond * 1000))[:int(frac)].rstrip('0')
        if digits:
            s += '.' + digits
    return s


def b24000_normalize_locations(locations=None):
    """把任意来源的行规整成 [{LocationId,Rank,Exp}]（int、按 LocationId 升序、去重）。

    官方 9 条的顺序就是 LocationId 升序，所以这里排序后输出，与官方一致。
    任何脏数据都不抛异常：解析不出来的行直接跳过，最后空了就退回最小实现。
    """
    rows = []
    src = locations if locations else B24000_DEFAULT_LOCATIONS
    for row in src:
        if isinstance(row, dict):
            try:
                loc = int(row.get('LocationId'))
            except Exception:
                continue
            try:
                rank = int(row.get('Rank', 1))
            except Exception:
                rank = 1
            try:
                exp = int(row.get('Exp', 0))
            except Exception:
                exp = 0
            rows.append({'LocationId': loc, 'Rank': rank, 'Exp': exp})
        elif isinstance(row, (list, tuple)) and len(row) >= 3:
            try:
                rows.append({'LocationId': int(row[0]), 'Rank': int(row[1]), 'Exp': int(row[2])})
            except Exception:
                continue
    if not rows:
        rows = [dict(r) for r in B24000_DEFAULT_LOCATIONS]
    rows.sort(key=lambda r: r['LocationId'])
    out = []
    seen = set()
    for r in rows:
        if r['LocationId'] in seen:
            continue
        seen.add(r['LocationId'])
        out.append(r)
    return out


def b24000_zone_keys(zone_scope='service', locations=None):
    """ZoneVisitCharacterDBs 的键（有序）。

    service（默认）：国服 9 个 location 的全部 zone = 71 个，= spec 的 key_count。
    account        ：只给本账号 AcademyLocationDBs 里出现过的 location 的 zone
                     （严格状态驱动；新号 1 条地点时是 8 个键，spec 会 WARN 长度越界）
    """
    if str(zone_scope) == 'account':
        locs = []
        for row in (locations or ()):
            try:
                locs.append(int(row.get('LocationId')))
            except Exception:
                continue
        if not locs:
            locs = list(B24000_ENABLED_LOCATIONS)
        keys = set()
        for loc in locs:
            for z in B24000_ZONE_BY_LOCATION.get(loc, ()):
                keys.add(str(z))
        return tuple(sorted(keys))
    return B24000_ZONE_KEY_ORDER


def b24000_academy_locations(account_id, locations=None):
    """AcademyLocationDBs 的行：严格 4 键 {AccountId,LocationId,Rank,Exp}（spec key_count=4）。"""
    aid = int(account_id)
    return [{'AccountId': aid, 'LocationId': r['LocationId'], 'Rank': r['Rank'], 'Exp': r['Exp']}
            for r in b24000_normalize_locations(locations)]


def b24000_build(account_id, mxtoken, request_id, ticks,
                 locations=None, last_update=None, zone_scope='service', zone_visit=None):
    """渲染完整的 24000 响应。

    account_id : int   AccountServerId（也是 AcadeyDB.AccountId）
    mxtoken    : str   SessionKey.MxToken（官方 64 字符 base64）
    request_id : str   外层 requestid 与它必须**同值**（官方 outer == inner）
    ticks      : int   .NET 100ns ticks
    locations  : 可选的 AcademyLocationDBs 行；None = 最小实现（1 条 1/1/0）
    last_update: 可选 ISO 字符串；None = 由 ticks 反推（同一墙钟坐标系）
    zone_scope : 'service'（71 键，默认）/ 'account'（只给本账号地点）
    zone_visit : 可选 {zone_key: [ {UniqueId,ServerId,LastInteractTime}, ... ]}，
                 只保留 b24000_zone_keys() 里存在的键，用于把状态接进来
    """
    aid = int(account_id)
    nlt = int(ticks)
    rows = b24000_normalize_locations(locations)
    if last_update is None:
        last_update = b24000_fmt_time(b24000_time_from_ticks(nlt))

    zone_visit = zone_visit or {}
    zv = {}
    for k in b24000_zone_keys(zone_scope, rows):
        vals = zone_visit.get(k)
        zv[k] = [dict(el) for el in vals if isinstance(el, dict)] if vals else []

    return {
        'Protocol': B24000_PROTO,
        'SessionKey': {'AccountServerId': aid, 'MxToken': str(mxtoken or '')},
        'ServerTimeTicks': nlt,
        'ServerNotification': 0,
        'RequestId': str(request_id or ''),
        'AcademyDB': {
            'AccountId': aid,
            'LastUpdate': str(last_update),
            'ZoneVisitCharacterDBs': zv,
            'ZoneScheduleGroupRecords': {},
        },
        'AcademyLocationDBs': b24000_academy_locations(aid, rows),
    }


def b24000_compact(obj):
    """紧凑 JSON（wire 里 packet 的实际序列化方式）。"""
    import json as _json
    return _json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def b24000_check(obj):
    """结构自检，返回 dict（不抛异常）：ok / problems / 各项计数。"""
    out = {'ok': False, 'problems': [], 'top_keys': [], 'zone_keys': 0,
           'locations': 0, 'inner_bytes': 0, 'rid_len': 0, 'token_len': 0}
    try:
        if not isinstance(obj, dict):
            out['problems'].append('根节点不是 dict: %s' % type(obj).__name__)
            return out
        keys = tuple(obj.keys())
        out['top_keys'] = list(keys)
        if keys != B24000_TOP_KEYS:
            out['problems'].append('顶层键/键序不符: %r != %r' % (list(keys), list(B24000_TOP_KEYS)))
        if obj.get('Protocol') != B24000_PROTO:
            out['problems'].append('Protocol=%r' % (obj.get('Protocol'),))
        sk = obj.get('SessionKey')
        if not isinstance(sk, dict) or tuple(sk.keys()) != ('AccountServerId', 'MxToken'):
            out['problems'].append('SessionKey 形状不符: %r' % (sk,))
        else:
            if not isinstance(sk.get('AccountServerId'), int):
                out['problems'].append('SessionKey.AccountServerId 不是 int')
            out['token_len'] = len(str(sk.get('MxToken') or ''))
        if not isinstance(obj.get('ServerTimeTicks'), int):
            out['problems'].append('ServerTimeTicks 不是 int')
        if obj.get('ServerNotification') != 0:
            out['problems'].append('ServerNotification 应为 0')
        rid = obj.get('RequestId')
        if not isinstance(rid, str) or not rid:
            out['problems'].append('RequestId 为空或非字符串')
        out['rid_len'] = len(rid) if isinstance(rid, str) else 0

        adb = obj.get('AcademyDB')
        if not isinstance(adb, dict):
            out['problems'].append('AcademyDB 不是 dict')
        else:
            if tuple(adb.keys()) != ('AccountId', 'LastUpdate', 'ZoneVisitCharacterDBs',
                                     'ZoneScheduleGroupRecords'):
                out['problems'].append('AcademyDB 键/键序不符: %r' % (list(adb.keys()),))
            if not isinstance(adb.get('AccountId'), int):
                out['problems'].append('AcademyDB.AccountId 不是 int')
            if not isinstance(adb.get('LastUpdate'), str) or 'T' not in str(adb.get('LastUpdate')):
                out['problems'].append('AcademyDB.LastUpdate 形态不符: %r' % (adb.get('LastUpdate'),))
            zv = adb.get('ZoneVisitCharacterDBs')
            if not isinstance(zv, dict):
                out['problems'].append('ZoneVisitCharacterDBs 不是 dict（必须是 map<string,array>）')
            else:
                out['zone_keys'] = len(zv)
                if not all(isinstance(v, list) for v in zv.values()):
                    out['problems'].append('ZoneVisitCharacterDBs 存在非数组值')
                if not all(str(k).lstrip('-').isdigit() for k in zv):
                    out['problems'].append('ZoneVisitCharacterDBs 存在非数字键')
                if len(zv) == len(B24000_ZONE_KEY_ORDER) and tuple(zv.keys()) != B24000_ZONE_KEY_ORDER:
                    out['problems'].append('ZoneVisitCharacterDBs 键序不是字典序')
            if adb.get('ZoneScheduleGroupRecords') != {}:
                out['problems'].append('ZoneScheduleGroupRecords 必须为空对象 {}')

        locs = obj.get('AcademyLocationDBs')
        if not isinstance(locs, list) or not locs:
            out['problems'].append('AcademyLocationDBs 为空或非数组')
        else:
            out['locations'] = len(locs)
            for i, row in enumerate(locs):
                if not isinstance(row, dict):
                    out['problems'].append('AcademyLocationDBs[%d] 不是 dict' % i)
                    continue
                if tuple(row.keys()) != ('AccountId', 'LocationId', 'Rank', 'Exp'):
                    out['problems'].append('AcademyLocationDBs[%d] 键/键序不符: %r'
                                           % (i, list(row.keys())))
                for k in ('AccountId', 'LocationId', 'Rank', 'Exp'):
                    if not isinstance(row.get(k), int):
                        out['problems'].append('AcademyLocationDBs[%d].%s 不是 int' % (i, k))
        out['inner_bytes'] = len(b24000_compact(obj).encode('utf-8'))
        out['ok'] = not out['problems']
    except Exception as e:            # 自检本身不允许把调用方拖死
        out['problems'].append('check 异常: %r' % (e,))
        out['ok'] = False
    return out
# ==== END ENGINE CORE (24000 v2) ====
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


def _ba24000_session_key(rec=None):
    """桥里缓存的会话（来自 CheckNexon 的真实 SessionKey，MxToken 是 64 字符 base64）。

    [BAPATCH-MULTIACCT v1] 取"本请求那个账号"的桶；开关关时 acct_session() 就是基线单例。
    """
    try:
        sk = getattr(acct_session(rec), 'session_key', None)
    except Exception:
        return None
    return sk if isinstance(sk, dict) else None


def _ba24000_pick_account(text, cfg, rec=None):
    """账号优先级：请求体 AccountId > 请求体 SessionKey.AccountServerId > 会话 > 配置兜底。"""
    aid = _ba24000_find_int(text, 'AccountId')
    if aid:
        return aid, 'request.AccountId'
    aid = _ba24000_find_int(text, 'AccountServerId')
    if aid:
        return aid, 'request.SessionKey.AccountServerId'
    try:
        _sess = acct_session(rec)          # [BAPATCH-MULTIACCT v1] 本请求那个账号的桶
        if getattr(_sess, 'account_id', None):
            return int(_sess.account_id), 'session.account_id'
    except Exception:
        pass
    sk = _ba24000_session_key(rec)
    if sk:
        try:
            return int(sk.get('AccountServerId')), 'session.session_key'
        except Exception:
            pass
    try:
        return int(cfg.get('default_account_id') or 0), 'config.default_account_id'
    except Exception:
        return 0, 'config.default_account_id'


def _ba24000_pick_token(text, cfg, account_id, rec=None):
    """MxToken：请求体 > 会话 > 由账号派生（sha384->base64，恰好 64 字符，与官方同形）。"""
    tok = _ba24000_find_str(text, 'MxToken')
    if tok:
        return tok, 'request'
    sk = _ba24000_session_key(rec)
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
        aid, asrc = _ba24000_pick_account(text, cfg, rec)
        tok, tsrc = _ba24000_pick_token(text, cfg, aid, rec)
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
        aid = int(getattr(acct_session(rec), 'account_id', 0) or 0)   # [BAPATCH-MULTIACCT v1]
    except Exception:
        aid = 0
    sk = _ba24000_session_key(rec)
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
# ==== END 24000_v3 (managed block) ====


def _ensure_session_locked(sess, rec, ticket, pub=None):
    """ensure_session 的函数体（**基线原文**）：只把 SESSION 换成 sess、ENTER_TICKET 换成 ticket。

    开关关时调用方传的就是 (SESSION, ENTER_TICKET) —— 同一个对象、同一张票，
    所以这条路径与基线逐字等价（连 rec 里写的字段都一模一样）。

    pub（[PATCH-PY-20261118-sidwb]）：只有 ensure_session 的**分桶分支**会传；基线单例路径
    一律 pub=None ⇒ 不落库、不写 rec 新字段，行为与基线逐字一致。

    TTL（[BAPATCH-SESSTTL v1]）：上面那句"与基线逐字等价"以"会话没过期"为前提；TTL>0 且
    桶龄超过 ttl 时会清桶重铸（真打 1014），TTL<=0 时这条分支整块不生效。
    """
    with sess.lock:
        if want_force_reauth():
            rec['force_reauth'] = True
            sess.session_key = None
            sess.account_id = None
            clear_force()
        _ttl_drop = False                      # [BAPATCH-SESSTTL v1] 本次是否因"会话过期"重铸
        if sess.session_key is not None:
            # [BAPATCH-SESSTTL v1] 命中缓存前先看桶龄：now - (created or 0) > ttl 就算过期。
            #   TTL<=0（关闭）/ 读开关或算年龄抛异常 -> _ttl_age None -> 与基线逐字一致。
            _ttl_age = None
            try:
                _ttl = cn_session_ttl()
                if _ttl > 0:
                    _ttl_age = int(time.time()) - int(sess.created or 0)
            except Exception:
                _ttl_age = None
            if _ttl_age is not None and _ttl_age > _ttl:
                _ttl_drop = True
                sess.session_key = None        # 清的是"这个桶"（就在它自己的锁里）
                sess.account_id = None
                sess.created = 0
                try:
                    rec['session_source'] = 'expired'
                    rec['session_age'] = int(_ttl_age)
                except Exception:
                    pass
            if not _ttl_drop:
                rec['session_source'] = 'cache'
                return sess.session_key, sess.account_id
        req = {"Protocol": "Account_CheckNexon", "EnterTicket": ticket,
               "ClientGeneratedKey": CLIENT_KEY, "ClientGeneratedIV": CLIENT_IV}
        rec['synth_checknexon'] = req
        t0 = time.time()
        code, raw = post_gateway(req)
        rec['checknexon_code'] = code
        rec['checknexon_ms'] = int((time.time() - t0) * 1000)
        rec['checknexon_resp_len'] = len(raw)
        _, obj = unwrap_gateway_response(raw)
        if not isinstance(obj, dict) or not obj.get('SessionKey'):
            rec['checknexon_err'] = 'no SessionKey'
            rec['checknexon_resp'] = raw[:300].decode('utf-8', 'replace')
            return None, None
        sess.session_key = obj['SessionKey']
        sess.account_id = obj.get('AccountId') or obj['SessionKey'].get('AccountServerId')
        sess.created = int(time.time())
        rec['session_source'] = 'fresh'
        rec['session_key'] = sess.session_key
        rec['account_id'] = sess.account_id
        if _ttl_drop:
            # [BAPATCH-SESSTTL v1] 这次是"过期重铸"，不是首铸：session_source 记 expired 便于取证
            # （session_age 在判过期那里已经写入；真的打了 1014 有 rec['synth_checknexon'] 可查）。
            rec['session_source'] = 'expired'
        # [PATCH-PY-20261118-sidwb] 基线路径（pub=None）：原样在这里返回，一个字节都不动。
        if pub is None:
            return sess.session_key, sess.account_id
        _wb_key, _wb_sid = sess.session_key, sess.account_id
    # [PATCH-PY-20261118-sidwb] 新铸会话的 Shittim ServerId 回写，**放在 sess.lock 之外**：
    #   * 只有「新铸」才会走到这里 —— cache 命中在上面（sess.session_key is not None）就
    #     return 了，不会每次命中都写；
    #   * pub 只有 ensure_session 的分桶分支才传（开关关/解析不到 = None，永不进这里）；
    #   * 服务端连接是 thread-local（与 acct_apply_to_auth 同一根连接），本来就不构成 ABBA；
    #     放到锁外是为了别在 SQLite busy_timeout（5s）期间一直占着这把桶锁。
    try:
        _sid_writeback(pub, _wb_sid, rec)
    except Exception:
        pass
    return _wb_key, _wb_sid


def ensure_session(rec, pub=None):
    # [BAPATCH-BANEXP v1] 限时账号封禁的读侧自愈（只可能"解封"，不可能拦人；异常一律放行）
    banexp_gate(rec, pub)
    # [BAPATCH-MULTIACCT v1] 会话按账号分桶：
    #   开关关 / 解析不到 pub / pub==老账号 UID -> 走**基线路径**（单例 SESSION + 常量 ENTER_TICKET），
    #   一个字节都没动，连 enter_ticket() 都不调用；
    #   开关开且解析到账号 -> 每桶自己的 Session + 自己的 lock，票据用 enter_ticket(pub)，
    #   两个账号的首登互不阻塞、也不会覆盖对方的 session_key / account_id。
    # 持锁期间仍有那一次 post_gateway（与基线一致），但不同 publisher 用的是不同的锁。
    _on = False
    try:
        _on = cn_multiacct_on()
    except Exception:
        _on = False
    if not _on:
        return _ensure_session_locked(SESSION, rec, ENTER_TICKET)
    _pub = pub if pub is not None else acct_pub_for(rec)
    _key = _cn_pub_key(_pub)
    if not _key or _key == str(UID):
        # 解析不到身份，或就是老账号本人 —— 都走基线路径（老账号那张票必须逐字节不变）
        return _ensure_session_locked(SESSION, rec, ENTER_TICKET)
    _sess = acct_session(rec, _pub)
    if _sess is SESSION:
        if cn_multiacct_on():
            # 开关开、身份也解析出来了，却没拿到独立桶：宁可失败也**绝不**退回公共账号
            # （退回 = 把这个玩家的存档写进公共号 314816420，那是最坏的结果）。
            rec['acct_bucket_err'] = 'no-bucket'
            return None, None
        return _ensure_session_locked(SESSION, rec, ENTER_TICKET)
    return _ensure_session_locked(_sess, rec, enter_ticket(_pub), _pub)


def parse_cn_multipart(raw):
    out = {}
    for name in ('protocol', 'encode', 'packet'):
        key = ('name="%s"' % name).encode()
        i = raw.find(key)
        if i < 0:
            continue
        j = raw.find(b'\r\n\r\n', i)
        if j < 0:
            continue
        k = raw.find(b'\r\n--', j + 4)
        if k < 0:
            continue
        out[name] = raw[j + 4:k].decode('latin1').strip()
    return out


def encrypt_variant(inner_obj, variant, req_key):
    """Return (packet_b64, plaintext_that_was_encrypted).

    variant 1: WHOLE json inside ciphertext, Protocol as NUMBER
    variant 2: fragment only inside ciphertext (starts with ','), client prepends {"Protocol":<num>
    variant 3: WHOLE json inside ciphertext, but Protocol written as the NAME string
    """
    key = req_key.encode('ascii', 'replace') if isinstance(req_key, str) else req_key
    if not key:
        key = None
    if variant == 3:
        o = dict(inner_obj)
        o['Protocol'] = '__NAME__'
        full = json.dumps(o, ensure_ascii=False, separators=(',', ':'))
        full = full.replace('"__NAME__"', '%s' % json.dumps(o.get('Protocol')))
        inner = cn_cipher.build_inner(full, key=key)
        return cn_cipher.wrap_packet(inner), full
    full = json.dumps(inner_obj, ensure_ascii=False, separators=(',', ':'))
    if variant == 1:
        inner = cn_cipher.build_inner(full, key=key)
        return cn_cipher.wrap_packet(inner), full
    idx = full.find(',')
    frag = full[idx:] if idx >= 0 else full
    inner = cn_cipher.build_inner(frag, key=key)
    return cn_cipher.wrap_packet(inner), frag


# >>> BA-1017-DYNAMIC-PATCH v1  (work/ba/server/deploy/patch_1017.py)
# 1017 Account_LoginSync 动态生成 —— 运行时开关。
#   cn_1017_mode.txt 内容 'dynamic'（默认）/'legacy'；文件不存在 = dynamic。
#   环境变量 CN_1017_MODE 优先级更高（便于单次启动临时覆盖）。
CN_1017_MODE_FILE = '/www/wwwroot/bapatch/cn_1017_mode.txt'
GEN1017_DIR = os.environ.get('BA_GEN1017_DIR') or os.path.dirname(os.path.abspath(__file__))


def cn_1017_mode():
    v = (os.environ.get('CN_1017_MODE') or '').strip().lower()
    if v:
        return v
    try:
        v = open(CN_1017_MODE_FILE).read().strip().lower()
    except Exception:
        return 'dynamic'
    return v or 'dynamic'


def _gen1017_import():
    if GEN1017_DIR and GEN1017_DIR not in sys.path:
        sys.path.insert(0, GEN1017_DIR)
    import gen1017
    return gen1017

# <<< BA-1017-DYNAMIC-PATCH v1 <<<  (module level)
class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def _log(self, rec):
        try:
            with open(LOG, 'a') as f:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        except Exception:
            pass

    def _send(self, code, body, ctype='application/json; charset=utf-8', opts=None):
        try:
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            if opts and opts.get('no_transform'):
                self.send_header('Cache-Control', 'no-transform')
            if opts and opts.get('close'):
                self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(body)
            if opts and opts.get('close'):
                self.close_connection = True
        except Exception:
            pass

    def _log_ingress(self):
        try:
            cl = self.headers.get('Content-Length')
            ua = self.headers.get('User-Agent') or '-'
            rid = self.headers.get('REQUEST-ID') or self.headers.get('Request-Id') or '-'
            line = '%s | %-4s %-40s | CL=%-6s | UA=%-24s | RID=%s\n' % (
                time.strftime('%Y-%m-%d %H:%M:%S'), self.command, (self.path or '-')[:40],
                cl if cl else '-', ua[:24], rid)
            with open('/www/wwwroot/bapatch/logs/all_paths.log', 'a') as f:
                f.write(line)
        except Exception:
            pass

    def _handle(self):
        self._log_ingress()
        body, _body_code, _body_err = _read_request_body(self, MAX_REQUEST_BODY)
        if _body_code:
            self._log({'t': time.strftime('%Y-%m-%d %H:%M:%S'), 'path': self.path,
                       'method': self.command, 'err': 'BODY: ' + str(_body_err),
                       'resp_code': _body_code, 'resp_len': 0})
            self._send(_body_code, json.dumps({'error': _body_err}).encode(), 'application/json')
            return
        m = mode()
        rec = {'t': time.strftime('%Y-%m-%d %H:%M:%S'), 'from': self.client_address[0],
               'method': self.command, 'path': self.path, 'mode': m,
               'headers': {_k: (mask_secret(_v) if str(_k).lower() in SENSITIVE_KEYS else _v)
                        for _k, _v in self.headers.items()},
               'body_len': len(body),
               'body_printable': ''.join(chr(c) if 32 <= c < 127 else '.' for c in body[:1024])}
        t0 = time.time()
        try:
            if m == 'forward':
                code, resp, ctype = self._forward(body)
                rec['served'] = 'forward'
            else:
                code, resp, ctype = self._bridge(body, rec)
                rec['served'] = 'bridge'
        except Exception as e:
            rec['err'] = repr(e)
            code, resp, ctype = 500, json.dumps({'error': repr(e)}).encode(), 'application/json'
        # >>> BANREPLY2 FIX-A2 BEGIN >>>
        # 出口断言（只观测，不改一个字节的行为）：命中封禁却没走封禁包出口 => 又被覆盖了。
        # 监控红线：grep -c '"banreply_served": "MISS"' 必须恒为 0；不为 0 就是又被 _cn_enc_b64
        # 那一类"忽略入参"的编码器吞掉了（修 1 之前的形态），立刻回滚/排查。
        try:
            if rec.get('banreply') == 'hit' and not rec.get('banreply_served'):
                rec['banreply_served'] = 'MISS'
                acct_log('[banreply] MISS: hit but not served (path=%r wrap_mode=%r resp_len=%r)'
                         % (rec.get('path'), rec.get('wrap_mode'), len(resp)))
        except Exception:
            pass
        # <<< BANREPLY2 FIX-A2 END <<<
        ov = http_override()
        if ov:
            rec['http_override'] = ov
            if ov == 'http500':
                code = 500
            elif ov == 'http404':
                code = 404
            elif ov == 'http200empty':
                code, resp = 200, b''
            elif ov == 'http200':
                code = 200
        rec['ms'] = int((time.time() - t0) * 1000)
        rec['resp_code'] = code
        rec['resp_len'] = len(resp)
        rec['resp_printable'] = ''.join(chr(c) if 32 <= c < 127 else '.' for c in resp[:512])
        opts = rec.pop('_send_opts', None)
        self._log(rec)
        self._send(code, resp, ctype, opts)

    def _forward(self, body):
        url = TARGET_BASE + self.path
        req = urllib.request.Request(url, data=body if body else None, method=self.command)
        for k, v in self.headers.items():
            if k.lower() not in HOP:
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read(), r.headers.get('Content-Type', 'application/octet-stream')
        except urllib.error.HTTPError as e:
            return e.code, (e.read() if e else b''), 'application/octet-stream'

    # ---------- response helpers ----------
    def _cn_envelope(self, proto_name, inner_obj, rec):
        inner_obj = apply_field_patch(inner_obj, rec)
        inner_obj = apply_flatten(inner_obj, rec)
        if cn_wrap_mode() in ('cn_enc_b64', 'cn_enc_b64_probe', 'real_captured', 'e0_proto_swap', 'r01_update', 'e1_token', 'e2_nickname', 'e3_bare_dto', 'e4_strict_dto', 'a_proto_int', 'b_proto_str'):
            return self._cn_enc_b64(proto_name, inner_obj, rec)
        if cn_proto_val() == 'name':
            proto32 = proto_name
            rec['proto_val'] = 'name'
        else:
            proto32 = base64.b32encode(hashlib.md5(proto_name.encode('utf-16-le')).digest()).decode().rstrip('=')
            rec['proto_val'] = 'token'
        payload_text = json.dumps(inner_obj, ensure_ascii=False, separators=(',', ':'))
        payload = payload_text.encode('utf-8')
        if cn_packet_wrap() == 'json_string':
            wire = payload_text
            rec['packet_wrap'] = 'json_string'
        else:
            wire = cn_cipher.wrap_packet(payload)
            rec['packet_wrap'] = 'raw_gzip'
        rec['cn_envelope'] = True
        rec['cn_env_protocol'] = proto32
        rec['cn_env_payload_len'] = len(payload)
        rec['cn_env_wire_len'] = len(wire)
        out = {}
        if cn_canary_on():
            out["_cn_probe"] = "ZZCANARY7391QKVB"
            rec["canary"] = True
        out["protocol"] = proto32
        out["packet"] = wire
        if cn_canary_on():
            out["_cn_probe_tail"] = "ZZTAIL7391QKVB"
            rec["canary_tail"] = True
        if cn_hash_mode() == 'request':
            hv = rec.get("req_Hash")
            if hv is not None:
                out["Hash"] = hv
                rec["hash_echo"] = hv
                rec["hash_echo_type"] = type(hv).__name__
        return 200, json.dumps(out, ensure_ascii=False, separators=(',', ':')).encode(), \
            'application/json; charset=utf-8'

    def _cn_decode_any(self, packet_b64, proto_str):
        """Try cn_cipher first, fall back to a plain [u32][gzip][iv|ct|key] decode."""
        try:
            r = cn_cipher.decode_packet(packet_b64, proto_str)
            frag = r.get('fragment') or ''
            if frag:
                return frag
        except Exception as e1:
            self._last_decode_err = repr(e1)
        try:
            import base64 as _b64, gzip as _gz
            from cryptography.hazmat.primitives.ciphers import Cipher as _C, algorithms as _A, modes as _M
            raw = _b64.b64decode(packet_b64 + '=' * ((4 - len(packet_b64) % 4) % 4))
            inner = _gz.decompress(raw[4:])
            iv, ct, key = inner[:16], inner[16:-32], inner[-32:]
            d = _C(_A.AES(key), _M.CBC(iv)).decryptor()
            pt = d.update(ct) + d.finalize()
            pad = pt[-1]
            if 1 <= pad <= 16 and pt.endswith(bytes([pad]) * pad):
                pt = pt[:-pad]
            return pt.decode('utf-8', 'replace')
        except Exception as e2:
            self._last_decode_err = repr(e2)
            return ''

    def _generic_protocol_response(self, proto_str, packet_b64, rec, name=None):
        """Any protocol we do not implement -> decrypt the request, read Hash>>32, answer with a valid envelope."""
        frag = self._cn_decode_any(packet_b64, proto_str)
        rec['gen_frag_len'] = len(frag)
        if not frag:
            rec['gen_dec_err'] = getattr(self, '_last_decode_err', 'empty')
        num = None
        m = re.search(r'"Hash"\s*:\s*(\d+)', frag)
        if m:
            num = int(m.group(1)) >> 32
        rec['gen_protocol'] = num
        if rec.get('req_Hash') and num is None:
            try:
                num = int(rec['req_Hash']) >> 32
                rec['gen_protocol'] = num
            except Exception:
                pass
        if num is None:
            return None
        # >>> BAPATCH-SIMPLE-HOOK-G v1 BEGIN >>>
        # 1005 / 4000 / 26000: 官方结构（spec 驱动），替代下面 min+base 的 7 个假键
        # frag 用 locals().get() 取：线上 bridge 与本仓库副本不是同一版（45,470 vs 46,568 B），
        # 万一那版里这个局部变量不叫 frag，也不至于 NameError（最坏只是不回显 MxToken）。
        try:
            _sg = simple_route(rec, name, num, locals().get('frag'), cn_wire.wrap_response)
            if _sg is not None:
                return _sg
        except Exception as _sg_err:
            rec['simple_err'] = 'HOOK-G ' + repr(_sg_err)
        # <<< BAPATCH-SIMPLE-HOOK-G v1 END <<<
        # >>> BAPATCH-P3-HOOK-G v1 BEGIN >>>
        # protocol 3：泛接口兜底（min+base 假键）之前接管，回官方 7 键 / 620 B。
        # frag 用 locals().get()：万一别的版本里这个局部变量改名也不至于 NameError。
        try:
            _p3g = p3_route(rec, name, num, locals().get('frag'),
                            cn_wire.wrap_response, hook='HOOK-G')
            if _p3g is not None:
                return _p3g
        except Exception as _p3g_err:
            rec['p3_err'] = 'HOOK-G ' + repr(_p3g_err)
        # <<< BAPATCH-P3-HOOK-G v1 END <<<
        if num == 90004:
            from datetime import datetime as _d9
            import uuid as _uuid9
            _n9 = _d9.now()
            _t9 = int((_n9 - _d9(1, 1, 1)).total_seconds()) * 10_000_000 + _n9.microsecond * 10
            _sk9 = getattr(SESSION, 'session_key', None)
            if not isinstance(_sk9, dict):
                _sk9 = {}
            _sk9 = {'AccountServerId': _sk9.get('AccountServerId')
                                  or getattr(SESSION, 'account_id', 0) or 0,
                    'MxToken': _sk9.get('MxToken') or ''}
            _rid9 = pick_requestid(rec) or str(_uuid9.uuid4())
            if not rec.get('requestid_source'):
                rec['requestid_source'] = 'random'
            obj = build_90004_management_data(_sk9, _t9, _rid9, load_90004_ops())
            rec['gen_kind'] = 'management-90004-official'
            rec['fallback'] = 'generic-envelope'
            rec['gen_90004_data_keys'] = len(obj.get('Data') or {})
            rec['gen_90004_bytes'] = len(json.dumps(obj, ensure_ascii=False,
                                                        separators=(',', ':')))
            _r9 = data_key_report(obj)
            rec['gen_90004_lists'] = dict((k, _r9[k]) for k in (
                'Notices', 'Events', 'Issues', 'Banners',
                'GachaProbabilityDisplay', 'GuidePopup'))
            return self._cn_send_envelope(name or 'Management_Data', obj, rec)
        if num == 24000:
            obj = _ba24000_build(frag if 'frag' in locals() else '', rec)
            rec['gen_kind'] = 'academy-24000-v3'
            rec['gen_v'] = 'v3'
            rec['fallback'] = 'dynamic-24000'
            return _ba24000_send(name or 'Academy_GetInfo', obj, rec)
# >>> BA-1017-DYNAMIC-PATCH v1  (work/ba/server/deploy/patch_1017.py)
# 1017 走动态生成器（35 键 / 26 具名子回包 / 无 Responses 数组）。
# 关掉开关（--legacy）或任何异常 → 静默落到下面**未改动**的旧 492 B 分支。
        if num == 1017 and cn_1017_mode() != 'legacy':
            try:
                import uuid as _u1017
                _rid = str(_u1017.uuid4())
                _sess1017 = acct_session(rec)          # [BAPATCH-MULTIACCT v1] 本请求那个账号的桶
                _sk = _sess1017.session_key or {}
                _sid = _sk.get('AccountServerId') or _sess1017.account_id or 0
                _obj = _gen1017_import().build(
                    account_state={'server_id': _sid},
                    session=_sk,
                    request_id=_rid)
                _obj['RequestId'] = _rid      # inner == outer requestid（官方逐字节相同）
                _nm = name if (name and name != 'Unknown') else 'Account_LoginSync'
                _wire, _plain, _key = cn_wire.wrap_response(_nm, _obj, _rid)
                rec['gen_kind'] = 'loginsync-1017-dynamic'
                rec['fallback'] = 'gen1017'
                rec['wrap_mode'] = 'direct_envelope'
                rec['enc_requestid'] = _rid
                rec['enc_inner_keys'] = len(_obj)
                rec['gen1017_inner_len'] = _gen1017_import().measure(
                    _obj, _nm, _rid)['inner']
                rec['enc_plain_len'] = len(_plain)
                rec['enc_body_len'] = len(_wire)
                rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
                return 200, _wire, 'text/plain; charset=utf-8'
            except Exception as _e1017:
                rec['gen1017_err'] = repr(_e1017)

# <<< BA-1017-DYNAMIC-PATCH v1 <<<  (1017 dispatch)
        if num in (1019, 1017):
            obj = {"Protocol": 1019, "ServerTimeTicks": 0, "ServerNotification": 0,
                   "MissionProgressDBs": [], "EventMissionProgressDBDict": {},
                   "BattlePassMissionProgressDBDict": {}, "StaticOpenConditions": [],
                   "Responses": [], "SkillCutInOption": ""}
            rec['gen_kind'] = 'loginsync-%d' % num
            obj['Protocol'] = num
        else:
            from datetime import datetime as _dt
            _now = _dt.now()
            _ticks = int((_now - _dt(1, 1, 1)).total_seconds()) * 10_000_000 + _now.microsecond * 10
            obj = {"Protocol": num,
                   "ServerTimeTicks": _ticks,
                   "ServerNotification": 0,
                   "MissionProgressDBs": [],
                   "EventMissionProgressDBDict": {},
                   "BattlePassMissionProgressDBDict": {},
                   "StaticOpenConditions": []}
            rec['gen_kind'] = 'min+base'
        rec['fallback'] = 'generic-envelope'
        return self._cn_send_envelope(name or 'Unknown', obj, rec)

    def _cn_send_envelope(self, proto_name, obj, rec):
        """Encode exactly the object we were given (no cn_wrap_mode re-building)."""
        import uuid as _uuid
        rid = (obj.get('RequestId') if isinstance(obj, dict) else '') or str(_uuid.uuid4())  # 90004-PATCH: outer requestid = inner RequestId
        wire, plain, key = cn_wire.wrap_response(proto_name, obj, rid)
        rec['wrap_mode'] = 'direct_envelope'
        rec['enc_requestid'] = rid
        rec['enc_inner_keys'] = len(obj) if isinstance(obj, dict) else 0
        rec['enc_plain_len'] = len(plain)
        rec['enc_body_len'] = len(wire)
        rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
        try:
            open('/www/wwwroot/_ba_state/last_direct_envelope_plain.txt', 'w').write(plain)
        except Exception:
            pass
        return 200, wire, 'text/plain; charset=utf-8'

    def _cn_enc_b64(self, proto_name, inner_obj, rec):
        import uuid as _uuid
        if cn_wrap_mode() in ('a_proto_int', 'b_proto_str'):
            pv = 1002 if cn_wrap_mode() == 'a_proto_int' else 'Account_Auth'
            inner = cn_inner27.build(pv)
            inner = acct_apply_to_auth(inner, rec)
            rid = str(_uuid.uuid4())
            wire, plain, key = cn_wire.wrap_response('Account_Auth', inner, rid)
            rec['wrap_mode'] = cn_wrap_mode()
            rec['ab_protocol_value'] = pv
            rec['ab_inner_keys'] = len(inner)
            rec['enc_requestid'] = rid
            rec['enc_inner_keys'] = len(inner)
            rec['enc_plain_len'] = len(plain)
            rec['enc_body_len'] = len(wire)
            rec['canary_skipped'] = True
            rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
            try:
                tag = 'A' if cn_wrap_mode() == 'a_proto_int' else 'B'
                open('/www/wwwroot/_ba_state/round18_%s_wire.bin' % tag, 'wb').write(wire)
                open('/www/wwwroot/_ba_state/round18_%s_plain.txt' % tag, 'w').write(plain)
                rec['wire_dumped'] = True
            except Exception as e:
                rec['wire_dump_err'] = repr(e)
            return 200, wire, 'text/plain; charset=utf-8'
        if cn_wrap_mode() == 'e4_strict_dto':
            # strict DTO: ONLY members that really exist on AccountAuthResponse / ResponsePacket.
            # 'Protocol' lives on the HttpMessage wrapper layer -> must NOT appear here.
            inner = cn_inner.build(with_canary=False)
            inner.pop('Protocol', None)
            inner.pop('_probe', None)
            if cn_canary_on():
                inner['Desc'] = 'ZZCANARY7391QKVB'
                rec['canary_in_desc'] = True
            rid = str(_uuid.uuid4())
            wire, plain, key = cn_wire.wrap_response('Account_Auth', inner, rid)
            rec['wrap_mode'] = 'e4_strict_dto'
            rec['enc_requestid'] = rid
            rec['enc_inner_keys'] = len(inner)
            rec['enc_plain_len'] = len(plain)
            rec['enc_body_len'] = len(wire)
            rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
            try:
                open('/www/wwwroot/_ba_state/round17_wire_actual.bin', 'wb').write(wire)
                open('/www/wwwroot/_ba_state/round17_plain_actual.txt', 'w').write(plain)
                rec['wire_dumped'] = True
            except Exception as e:
                rec['wire_dump_err'] = repr(e)
            return 200, wire, 'text/plain; charset=utf-8'
        if cn_wrap_mode() == 'e3_bare_dto':
            inner = cn_inner.build(with_canary=cn_canary_on())
            plaintext = json.dumps(inner, ensure_ascii=False, separators=(',', ':'))
            wire, plain, key = cn_wire.wrap_raw(plaintext)
            rec['wrap_mode'] = 'e3_bare_dto'
            rec['e3_keys'] = len(inner)
            rec['enc_inner_keys'] = len(inner)
            rec['enc_plain_len'] = len(plain)
            rec['enc_body_len'] = len(wire)
            rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
            try:
                open('/www/wwwroot/_ba_state/round16_wire_actual.bin', 'wb').write(wire)
                open('/www/wwwroot/_ba_state/round16_plain_actual.txt', 'w').write(plain)
                rec['wire_dumped'] = True
            except Exception as e:
                rec['wire_dump_err'] = repr(e)
            return 200, wire, 'text/plain; charset=utf-8'
        if cn_wrap_mode() == 'e2_nickname':
            inner = cn_inner.build(with_canary=cn_canary_on())
            inner['AccountDB']['Nickname'] = 'Sensei'
            rid = str(_uuid.uuid4())
            wire, plain, key = cn_wire.wrap_response('Account_Auth', inner, rid)
            rec['wrap_mode'] = 'e2_nickname'
            rec['e2_nickname'] = 'Sensei'
            rec['enc_requestid'] = rid
            rec['enc_inner_keys'] = len(inner)
            rec['enc_plain_len'] = len(plain)
            rec['enc_body_len'] = len(wire)
            rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
            try:
                open('/www/wwwroot/_ba_state/round15_wire_actual.bin', 'wb').write(wire)
                open('/www/wwwroot/_ba_state/round15_plain_actual.txt', 'w').write(plain)
                rec['wire_dumped'] = True
            except Exception as e:
                rec['wire_dump_err'] = repr(e)
            return 200, wire, 'text/plain; charset=utf-8'
        if cn_wrap_mode() == 'e1_token':
            inner = cn_inner.build(with_canary=cn_canary_on())
            rid = str(_uuid.uuid4())
            TOKEN = '<REDACTED_TOKEN>'
            wire, plain, key = cn_wire.wrap_response(TOKEN, inner, rid)
            rec['wrap_mode'] = 'e1_token'
            rec['e1_protocol'] = TOKEN
            rec['enc_requestid'] = rid
            rec['enc_inner_keys'] = len(inner)
            rec['enc_plain_len'] = len(plain)
            rec['enc_body_len'] = len(wire)
            rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
            try:
                open('/www/wwwroot/_ba_state/round14_wire_actual.bin', 'wb').write(wire)
                open('/www/wwwroot/_ba_state/round14_plain_actual.txt', 'w').write(plain)
                rec['wire_dumped'] = True
            except Exception as e:
                rec['wire_dump_err'] = repr(e)
            return 200, wire, 'text/plain; charset=utf-8'
        if cn_wrap_mode() == 'r01_update':
            inner = cn_inner.build(with_canary=cn_canary_on())
            inner['UpdateRequired'] = True
            rid = str(_uuid.uuid4())
            wire, plain, key = cn_wire.wrap_response('Account_Auth', inner, rid)
            rec['wrap_mode'] = 'r01_update'
            rec['r01_UpdateRequired'] = True
            rec['enc_requestid'] = rid
            rec['enc_inner_keys'] = len(inner)
            rec['enc_plain_len'] = len(plain)
            rec['enc_body_len'] = len(wire)
            rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
            try:
                open('/www/wwwroot/_ba_state/round10_wire_actual.bin', 'wb').write(wire)
                open('/www/wwwroot/_ba_state/round10_plain_actual.txt', 'w').write(plain)
                rec['wire_dumped'] = True
            except Exception as e:
                rec['wire_dump_err'] = repr(e)
            return 200, wire, 'text/plain; charset=utf-8'
        if cn_wrap_mode() == 'e0_proto_swap':
            raw = open('/www/wwwroot/_ba_state/cn_real_capture/resp_1.body', 'rb').read().strip()
            real_outer, real_inner, _k, _pl = cn_wire.unwrap_response(raw)
            rid = real_outer.get('requestid')
            wire, plain, key = cn_wire.wrap_response('Account_Auth', real_inner, requestid=rid)
            rec['wrap_mode'] = 'e0_proto_swap'
            rec['e0_requestid'] = rid
            rec['e0_real_packet'] = (real_outer.get('packet') or '')[:200]
            rec['e0_plain_len'] = len(plain)
            rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
            try:
                open('/www/wwwroot/_ba_state/round9_wire_actual.bin', 'wb').write(wire)
                open('/www/wwwroot/_ba_state/round9_plain_actual.txt', 'w').write(plain)
                rec['wire_dumped'] = True
            except Exception as e:
                rec['wire_dump_err'] = repr(e)
            return 200, wire, 'text/plain; charset=utf-8'
        if cn_wrap_mode() == 'real_captured':
            wire = open('/www/wwwroot/_ba_state/cn_real_capture/resp_1.body', 'rb').read().strip()
            rec['wrap_mode'] = 'real_captured'
            rec['real_captured_bytes'] = len(wire)
            rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
            try:
                open('/www/wwwroot/_ba_state/round8_wire_actual.bin', 'wb').write(wire)
                rec['wire_dumped'] = True
            except Exception as e:
                rec['wire_dump_err'] = repr(e)
            return 200, wire, 'text/plain; charset=utf-8'
        if cn_wrap_mode() == 'cn_enc_b64_probe':
            inner = {"Protocol": -1, "Reason": "ZZPROBEREASON", "ErrorCode": 1018}
            proto_name = "Error"
            rec['probe_mode'] = True
        elif cn_inner_src() == 'spec26':
            inner = cn_inner.build(with_canary=cn_canary_on())
            rec['inner_src'] = 'spec26'
        else:
            inner = dict(inner_obj)
            rec['inner_src'] = 'shittim'
        if cn_canary_on() and not rec.get('probe_mode') and rec.get('inner_src') != 'spec26':
            inner['_probe'] = 'ZZCANARY7391QKVB'
            rec['canary_inner'] = True
        if rec.get('inner_src') != 'spec26':
            inner = apply_min_inner(inner, rec)
        rid = pick_requestid(rec) or str(_uuid.uuid4())
        wire, plain, key = cn_wire.wrap_response(proto_name, inner, rid)
        rec['wrap_mode'] = 'cn_enc_b64'
        rec['enc_requestid'] = rid
        rec['enc_inner_keys'] = len(inner)
        rec['enc_plain_len'] = len(plain)
        rec['enc_body_len'] = len(wire)
        rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True,
                             'no_transform': len(wire) >= 1000}
        try:
            open('/www/wwwroot/_ba_state/round7_wire_actual.bin', 'wb').write(wire)
            open('/www/wwwroot/_ba_state/round7_plain_actual.txt', 'w').write(plain)
            rec['wire_dumped'] = True
        except Exception as e:
            rec['wire_dump_err'] = repr(e)
        return 200, wire, 'text/plain; charset=utf-8'

    def _json_ok(self, proto_name, inner_obj):
        inner_obj = apply_field_patch(inner_obj)
        out = {"protocol": proto_name,
               "packet": json.dumps(inner_obj, ensure_ascii=False, separators=(',', ':'))}
        return 200, json.dumps(out, ensure_ascii=False, separators=(',', ':')).encode(), \
            'application/json; charset=utf-8'

    def _json_encrypted(self, proto_name, inner_obj, exp, req_key, rec):
        variant = 1
        if exp.endswith('2'):
            variant = 2
        elif exp.endswith('3'):
            variant = 3
        pkt, plain = encrypt_variant(inner_obj, variant, req_key)
        rec['encresp'] = True
        rec['encresp_key'] = req_key
        rec['encresp_variant'] = variant
        rec['encresp_inner_len'] = len(pkt)
        rec['encresp_plain_len'] = len(plain)
        rec['encresp_prefix'] = plain[:40]
        out = {"protocol": proto_name, "packet": pkt}
        return 200, json.dumps(out, ensure_ascii=False, separators=(',', ':')).encode(), \
            'application/json; charset=utf-8'

    # ---------- main bridge ----------
    def _bridge(self, body, rec):
        fields = parse_cn_multipart(body)
        proto_str = fields.get('protocol', '')
        packet_b64 = fields.get('packet', '')
        if not packet_b64 and b'packet=' in body:
            try:
                from urllib.parse import parse_qs
                # base64 '+' would be decoded as space by parse_qs -> protect it first
                q = parse_qs(body.decode('utf-8', 'replace').replace('+', '%2B'))
                proto_str = (q.get('protocol') or [''])[0] or proto_str
                packet_b64 = (q.get('packet') or [''])[0] or packet_b64
                rec['form_encoded'] = True
            except Exception as e:
                rec['form_parse_err'] = repr(e)
        exp = exp_flag()
        rec['protocol_raw'] = proto_str
        rec['exp'] = exp
        name = name_fix_resolve(proto_str, rec)   # BAPATCH-NAME-FIX v1
        # >>> BAPATCH-BANREPLY v1 Hook BEGIN >>>
        # 位置：name 一确定就判，billing 止血 / dedup 回放 / p3 / relay / path A~D **全部之前**。
        # 为什么在这里：
        #   · 比 ensure_session 早 —— 被封的号 State=2，打 1014 会被守卫拒（500），那就轮不到弹窗了；
        #   · 比 billing_block / dedup 早 —— 不许任何既有拦截或旧缓存抢先回包；
        #   · 比 path A 早 —— 不依赖 cn_bridge_exp.txt 是否 decrypt+（线上是空 = path B）；
        #   · 身份靠自己解包（_cn_decode_any，只读）拿 fragment，所以不依赖 _FRAG_TLS 是否已填。
        # 开关关 / 未命中 -> 返回 None，后面一个字节都不变。
        try:
            _br = banreply_response(self, rec, name, packet_b64, proto_str)
            if _br is not None:
                return _br
        except Exception as _br_err:
            rec['banreply_err'] = 'hook ' + repr(_br_err)
        # <<< BAPATCH-BANREPLY v1 Hook END <<<
        # BAPATCH-BILLINGBLOCK v1: 付费礼包止血（开关开时直接拒绝，不转发、不拉 SDK）
        _bb = billing_block_response(self, name, rec)
        if _bb is not None:
            return _bb

        # BAPATCH-DEDUP v1: order dedupe (replay cached response instead of relaying again)
        _dd = dedup_replay(name, rec)
        if _dd is not None:
            return _dd

        rec['protocol_name'] = name
        # >>> BAPATCH-P3-HOOK-E v1 BEGIN >>>
        # protocol 3 (NetworkTime_Sync)：在 exp / path A 之前按协议名最早接管，
        # 保证 ReceiveTick / EchoSendTick 一定是真时间戳（红线：不能是通用空构造里的 0）。
        # 先 p3_name_hit（一次字符串比较）挡住别的协议，命中才读开关文件。
        # 开关关 / 生成器异常 -> 原路返回，后面的 path D / generic 兜底完全不变。
        try:
            if p3_name_hit(name) and p3_wants(3):
                _p3e = p3_route(rec, name, 3,
                                self._cn_decode_any(packet_b64, proto_str),
                                cn_wire.wrap_response, hook='HOOK-E')
                if _p3e is not None:
                    return _p3e
        except Exception as _p3e_err:
            rec['p3_err'] = 'HOOK-E ' + repr(_p3e_err)
        # <<< BAPATCH-P3-HOOK-E v1 END <<<

        if exp == 'experror':
            env = json.dumps({"protocol": "Error",
                              "packet": json.dumps({"Protocol": -1, "ErrorCode": 500,
                                                    "ServerTimeTicks": 639302206010000000},
                                                   separators=(',', ':'))},
                             separators=(',', ':'))
            return 200, env.encode(), 'application/json; charset=utf-8'

        if name is None:
            rec['unknown_protocol'] = True
            # >>> BAPATCH-RELAY-HOOK-A v1 BEGIN >>>
            # 未知协议：开关打开时把解出来的客户端真实请求转发给本地 Shittim
            # (/api/gateway)，拿到 dict 回包就用 _cn_envelope 包成 CN 信封返回。
            # 任何一步不成就原路落回（下面的 min+base / forward 完全不变，绝不 500）。
            # 已知协议（含 3/1005/1017/1019/24000/26000/4000/90004）在 relay_route
            # 里由 RL_HANDLED 显式排除；Account_CheckNexon(1014) 只由 ensure_session
            # 内部调用，不会经过这里。开关 cn_relay_unknown.txt 缺失 = 关。
            try:
                _rl_a = rl_route(rec, proto_str, packet_b64, name,
                                 lambda _nm, _obj, _rec: self._cn_send_envelope(
                                     name_fix_resolve(proto_str, _rec) or _nm, _obj, _rec))   # FIX-3 v1
                if _rl_a is not None:
                    return _rl_a
            except Exception as _rl_a_err:
                rec['relay_err'] = repr(_rl_a_err)
                rec['relay_fallthrough'] = 'exception'
            # <<< BAPATCH-RELAY-HOOK-A v1 END <<<
            got = self._generic_protocol_response(proto_str, packet_b64, rec)
            if got is not None:
                return got
            code, resp, ctype = self._forward(body)
            rec['fallback'] = 'forward-unknown-protocol'
            return code, resp, ctype

        want_decrypt = exp.startswith('decrypt+')

        # -------- path A: decrypt the real client request --------
        if want_decrypt and packet_b64:
            try:
                r = cn_cipher.decode_packet(packet_b64, proto_str)
            except Exception as e:
                rec['decrypt_err'] = repr(e)
                r = None
            if r is not None:
                rec['decrypted'] = True
                rec['req_key'] = mask_secret(r.get('key'))
                rec['req_iv'] = mask_secret(r.get('iv'))
                rec['req_inner_len'] = r.get('inner_len')
                rec['req_frag_len'] = r.get('frag_len')
                try:
                    _FRAG_TLS.v = r.get('fragment') or None
                    _FRAG_TLS.seq = _req_seq(rec)      # [修 3] 单调序号，替代 id(rec)（地址会被复用）
                except Exception:
                    _FRAG_TLS.v = None
                    _FRAG_TLS.seq = None
                req_json = r.get('json')
                if isinstance(req_json, dict):
                    rec['req_keys'] = sorted(req_json.keys())
                    try:
                        rec['req_frag_head'] = mask_secret(str(r.get('fragment'))[:600])
                    except Exception:
                        rec['req_frag_head'] = mask_secret('')
                    rec['req_Token'] = mask_secret(req_json.get('Token'))
                    rec['req_Hash'] = req_json.get('Hash')
                    sk, aid = ensure_session(rec)
                    if sk is None:
                        return 500, json.dumps({'error': 'checknexon failed'}).encode(), 'application/json'
                    injected = 'SessionKey' not in req_json
                    if injected:
                        req_json['SessionKey'] = sk
                    rec['session_injected'] = injected
                    code, raw = post_gateway(req_json)
                    rec['auth_code'] = code
                    rec['auth_resp_len'] = len(raw)
                    gp, obj = unwrap_gateway_response(raw)
                    rec['auth_protocol'] = gp
                    if not isinstance(obj, dict):
                        return 502, raw, 'application/json'
                    rec['auth_keys'] = sorted(obj.keys())[:25]
                    rec['resp_name'] = name
                    if cn_resp_format() == 'cn_envelope':
                        return self._cn_envelope(name, obj, rec)
                    if exp.endswith('encresp1') or exp.endswith('encresp2') or exp.endswith('encresp3'):
                        return self._json_encrypted(name, obj, exp, r.get('key'), rec)
                    return self._json_ok(name, obj)
                rec['decrypt_json_none'] = True
            rec['fallback'] = 'synthetic'
        # -------- path B: synthetic --------
        if name in ('Account_CheckNexon',):
            sk, aid = ensure_session(rec)
            if sk is None:
                return 500, json.dumps({'error': 'checknexon failed'}).encode(), 'application/json'
            obj = {"Protocol": 1014, "ResultState": 1, "SessionKey": sk, "AccountId": aid}
            return self._json_ok('Account_CheckNexon', obj)
        if name in ('Account_Auth', 'Account_Auth2'):
            sk, aid = ensure_session(rec)
            if sk is None:
                return 500, json.dumps({'error': 'checknexon failed'}).encode(), 'application/json'
            req = {"Protocol": "Account_Auth", "SessionKey": sk}
            rec['synth_auth'] = req
            code, raw = post_gateway(req)
            rec['auth_code'] = code
            rec['auth_resp_len'] = len(raw)
            gp, obj = unwrap_gateway_response(raw)
            if not isinstance(obj, dict):
                return 502, raw, 'application/json'
            rec['auth_keys'] = sorted(obj.keys())[:25]
            rec['exp_result_before'] = obj.get('ResultState')
            if cn_resp_format() == 'cn_envelope':
                return self._cn_envelope('Account_Auth', obj, rec)
            if exp in ('resultstate0', 'resultstate1'):
                obj['ResultState'] = 0 if exp == 'resultstate0' else 1
            return self._json_ok('Account_Auth', obj)
        # -------- path C0: Account_CallName (1010) --------
        if name == 'Account_CallName':
            call = '111'
            try:
                r0 = cn_cipher.decode_packet(packet_b64, proto_str)
                frag0 = r0.get('fragment') or ''
                rec['call_frag_len'] = len(frag0)
                m0 = re.search(r'"CallName"\s*:\s*"([^"]*)"', frag0)
                if m0:
                    call = m0.group(1)
                    rec['call_from_request'] = True
            except Exception as e:
                rec['call_dec_err'] = repr(e)
            rec['callname'] = call
            acct_writeback(rec, call_name=call)
            obj = cn_nick.build_callname_response(call, nickname='111', protocol=1010)
            rec['call_resp_accountdb_fields'] = len(obj['AccountDB'])
            return self._cn_send_envelope('Account_CallName', obj, rec)

        # -------- path C: Account_Nickname (1001) --------
        if name in ('Account_Nickname', 'Account_CallName'):
            frag = rec.get('req_frag_head') or ''
            if not frag:
                try:
                    r1 = cn_cipher.decode_packet(packet_b64, proto_str)
                    frag = r1.get('fragment') or ''
                    rec['nick_frag_len'] = len(frag)
                except Exception as e:
                    rec['nick_dec_err'] = repr(e)
            m = re.search(r'"Nickname"\s*:\s*"([^"]*)"', frag)
            nick = m.group(1) if m else '111'
            rec['nick_from_request'] = bool(m)
            rec['nickname'] = nick
            acct_writeback(rec, nickname=nick)
            obj = cn_nick.build_nickname_response(nick, protocol=1001)
            rec['nick_resp_keys'] = len(obj)
            rec['nick_accountdb_fields'] = len(obj['AccountDB'])
            return self._cn_send_envelope('Account_Nickname', obj, rec)

        # -------- path D: generic non-empty fallback (never 200 + 0 bytes) --------
        proto_int = None
        try:
            h = rec.get('req_Hash')
            if isinstance(h, int) and h > 0:
                proto_int = h >> 32
        except Exception:
            proto_int = None
        # >>> BAPATCH-SIMPLE-HOOK-D v1 BEGIN >>>
        # 1005 / 4000 / 26000: path D 会把它们回成 {"Protocol":N} 单键，先在这里接管
        try:
            if simple_wants(proto_int):
                _sg = self._generic_protocol_response(proto_str, packet_b64, rec, name=name)
                if _sg is not None:
                    return _sg
        except Exception as _sg_err:
            rec['simple_err'] = 'HOOK-D ' + repr(_sg_err)
        # <<< BAPATCH-SIMPLE-HOOK-D v1 END <<<
        # >>> BAPATCH-P3-HOOK-D v1 BEGIN >>>
        # protocol 3：path D 会把它回成 {"Protocol":3} 单键（无 tick），先在这里接管。
        try:
            if p3_wants(proto_int):
                _p3d = p3_route(rec, name, proto_int,
                                self._cn_decode_any(packet_b64, proto_str),
                                cn_wire.wrap_response, hook='HOOK-D')
                if _p3d is not None:
                    return _p3d
        except Exception as _p3d_err:
            rec['p3_err'] = 'HOOK-D ' + repr(_p3d_err)
        # <<< BAPATCH-P3-HOOK-D v1 END <<<
        # >>> BAPATCH-RELAY2-HOOK v1 BEGIN >>>
        # 名字已知、但没有真生成器的协议（8000 / 1006 / 8006 / 90011 / 35003 / 16000 …）：
        # 开关 cn_relay_known.txt 打开时，把客户端真实请求转发给本地 Shittim
        # (/api/gateway)，拿到 dict 回包就用 _cn_envelope 包成 CN 信封返回。
        # 挂在这里（`if proto_int:` 之前、同级）等于同时接住两条空壳出口：
        #   proto_int 有值 -> 原本走下面的 min-envelope；为 None -> 走 _generic_protocol_response 的 min+base。
        # 任何一步不成就原路落回（下面的代码完全不变，绝不 500）。
        # 有真生成器的协议号由 RL2_HANDLED 显式排除；Account_CheckNexon(1014) 只由
        # ensure_session 内部调用，另有名字级排除 + 同线程重入保护。开关缺失 = 关。
        try:
            _rl2_a = rl2_route(rec, proto_str, packet_b64, name,
                               self._cn_send_envelope)   # FIX-3 relay2
            if _rl2_a is not None:
                return _rl2_a
        except Exception as _rl2_a_err:
            rec['relay2_err'] = repr(_rl2_a_err)
            rec['relay2_fallthrough'] = 'exception'
        # <<< BAPATCH-RELAY2-HOOK v1 END <<<
        if proto_int:
            obj = cn_nick.build_min_response(proto_int)
            rec['fallback'] = 'min-envelope'
            rec['fallback_protocol'] = proto_int
            proto_name = name if (name and name != 'Unknown') else 'Account_Nickname'
            return self._cn_send_envelope(proto_name, obj, rec)
        got = self._generic_protocol_response(proto_str, packet_b64, rec, name=name)
        if got is not None:
            rec['known_other_upgraded'] = True
            return got
        code, resp, ctype = self._forward(body)
        rec['fallback'] = 'forward-known-other'
        return code, resp, ctype

    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle

    def log_message(self, *a):
        pass


# >>> BAPATCH-SIMPLE-PAYLOAD v1 BEGIN >>> (deploy/simple_payload.py verbatim, sha256=871a78b7e049c8e95056013a3327ba90fb53b7c7a66552d66cec2b4ca31619a1) >>>
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
    """账号号优先级：SESSION.account_id -> 请求片段里的 AccountServerId -> 文件 -> 默认号。

    [BAPATCH-MULTIACCT v1] 第一档的"会话"现在取"本请求那个账号的桶"（acct_session(rec)）：
    开关关 / 解析不到 -> 仍是基线单例 SESSION，逐字不变；解析到 -> 该账号自己那份 Shittim 会话的
    account_id，于是 1005/4000/26000 这些合成回包里的 SessionKey 才是这个玩家的。
    """
    try:
        sess = acct_session(rec)                   # [BAPATCH-MULTIACCT v1] 本请求那个账号的桶
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
# <<< BAPATCH-SIMPLE-PAYLOAD v1 END <<<
# >>> BAPATCH-P3-PAYLOAD v1 BEGIN >>> (deploy/patch_3.py 内嵌 P3_PAYLOAD_SRC，sha256=ee55b4cd2c9bd01eda252fa1550935e3e2637a12600759a4ff9652045d60789a) >>>
# -*- coding: utf-8 -*-
"""NetworkTime_Sync (protocol 3) 载荷生成器 —— 内嵌进 bridge 的运行时真源。

与 deploy/gen3.py 的 build_3() 逐字节等价（patch_3.py --verify 用真生成器比对）：
    acct = Account(server_id, mxtoken, request_id, now)      # now 必须是 datetime
    obj  = build_3(acct)                                     # ReceiveTick == EchoSendTick
    顶层键序 = official_spec.json protocols["3"].top_key_order

官方 04_3 抓包（report/_tmp/official_decoded_201/04_3_api_networktime_sync.response.json）：
    inner 314 B / wire 620 B，7 键；
    ReceiveTick == EchoSendTick == 639304002554622693；
    ServerTimeTicks = ...705（比前两者大 12 ticks = 1.2 µs，同一次取时的抖动）；
    inner.RequestId == outer.requestid（同一个 uuid）。
请求 DTO 没有业务字段（只有 HttpMessage 外壳），所以服务端**没有**可回显的客户端 tick，
两个 tick 都填「收到请求那一刻」就是官方行为。

tick 口径 = 服务器本地墙钟（不是 UTC）：
    官方 ServerTimeTicks=639304002554622705 解出来是 2026-11-16T04:30:55.462，
    HAR 里同一条请求的 startedDateTime=2026-11-15T20:30:55.625Z（Unix 口径），
    _timeline.txt 的 Beijing 列写 04:30:55.625 —— 即官方发的是北京墙钟。
    客户端是北京设备，只有同口径才能算出 ≈0 的偏移；发 UTC 会整体差 8 小时。
    需要时可用 cn_3_ticks.txt 写 'utc' 覆盖。

约定（原样贴进 bridge 的模块命名空间，所以）：
  * 不写 from __future__ / 不写 if __name__ == '__main__'；
  * 只用标准库，且全部用 _p3* 别名 import，不污染 bridge 现有全局名；
  * import 期不碰文件系统、不碰网络。
"""
import base64 as _p3base64
import datetime as _p3dt
import hashlib as _p3hashlib
import os as _p3os
import re as _p3re
import uuid as _p3uuid

P3_PROTOCOL = 3
P3_NAME = 'NetworkTime_Sync'

# official_spec.json -> protocols["3"].top_key_order
# （patch_3.py --verify 会重新读 spec 并断言这张表没过期）
P3_ORDER = ('Protocol', 'SessionKey', 'ServerTimeTicks', 'ServerNotification',
            'RequestId', 'ReceiveTick', 'EchoSendTick')

P3_SWITCH_FILE = 'cn_3.txt'
P3_TICKS_FILE = 'cn_3_ticks.txt'
# 开关查找顺序：bridge 所在目录 -> 线上 tools/ -> 线上 bapatch/
P3_FALLBACK_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')
P3_DEFAULT_ACCOUNT = 10015354380
P3_EPOCH = _p3dt.datetime(1, 1, 1)


# ---------------------------------------------------------------- 开关 / 小工具
def p3_dirs():
    """开关文件的候选目录（有序）。"""
    out = []
    try:
        out.append(_p3os.path.dirname(_p3os.path.abspath(__file__)))
    except Exception:
        pass
    for d in P3_FALLBACK_DIRS:
        if d not in out:
            out.append(d)
    return out


def p3_read_file(fn, base=None):
    """读一个小开关文件 -> (路径, 内容)。找不到 -> (None, None)。"""
    dirs = ([base] if base else []) + p3_dirs()
    for d in dirs:
        if not d:
            continue
        p = _p3os.path.join(d, fn)
        try:
            with open(p, 'r') as fh:
                return p, fh.read().strip()
        except Exception:
            continue
    return None, None


def p3_switch_on(base=None):
    """协议 3 是否启用。缺失 / 读不到 / 内容不是真值 -> False（fail-safe）。"""
    _p, v = p3_read_file(P3_SWITCH_FILE, base)
    if v is None:
        return False
    return v.strip().lower() in ('1', 'on', 'true', 'yes')


def p3_wants(num, base=None):
    """协议号是 3 且开关打开 —— 给 bridge 的分发处做前置判断（不解密、不构包）。"""
    try:
        n = int(num)
    except Exception:
        return False
    return n == P3_PROTOCOL and p3_switch_on(base)


def p3_num(num=None, name=None):
    """协议号判定：Hash>>32 命中 3，或者外层 protocol 就是 NetworkTime_Sync。"""
    try:
        n = int(num)
    except Exception:
        n = None
    if n == P3_PROTOCOL:
        return P3_PROTOCOL
    if isinstance(name, str) and name == P3_NAME:
        return P3_PROTOCOL
    return None


def p3_name_hit(name):
    """廉价预判（不碰文件系统）：外层协议名就是 NetworkTime_Sync？

    HOOK-E 在**每个**请求上都会经过，所以先用一次字符串比较挡住其它协议，
    连开关文件都不读；只有命中协议 3 才去碰盘。
    """
    return isinstance(name, str) and name == P3_NAME


def p3_ticks_mode(base=None):
    _p, v = p3_read_file(P3_TICKS_FILE, base)
    if v and v.strip().lower() == 'utc':
        return 'utc'
    return 'local'


def p3_ticks(dt=None, mode='local'):
    """.NET ticks（100ns，自 0001-01-01）。整数运算，不经 float。"""
    if dt is None:
        if str(mode).lower() == 'utc':
            dt = _p3dt.datetime.now(_p3dt.timezone.utc).replace(tzinfo=None)
        else:
            dt = _p3dt.datetime.now()
    elif getattr(dt, 'tzinfo', None) is not None:
        if str(mode).lower() == 'utc':
            dt = dt.astimezone(_p3dt.timezone.utc).replace(tzinfo=None)
        else:
            dt = dt.astimezone().replace(tzinfo=None)
    delta = dt - P3_EPOCH
    return (delta.days * 86400 + delta.seconds) * 10000000 + delta.microseconds * 10


def p3_now(mode='local'):
    if str(mode).lower() == 'utc':
        return _p3dt.datetime.now(_p3dt.timezone.utc).replace(tzinfo=None)
    return _p3dt.datetime.now()


# ---------------------------------------------------------------- 账号 / 令牌
def p3_session_from_frag(frag):
    """从客户端请求片段里取 SessionKey（官方就是原样回显它）。"""
    sid = mx = None
    if isinstance(frag, str) and frag:
        m = _p3re.search(r'"AccountServerId"\s*:\s*(\d+)', frag)
        if m:
            sid = int(m.group(1))
        m = _p3re.search(r'"MxToken"\s*:\s*"([^"]{8,200})"', frag)
        if m:
            mx = m.group(1)
    return sid, mx


def p3_account_id(rec=None, frag=None):
    sid, _mx = p3_session_from_frag(frag)
    if sid:
        return int(sid)
    try:
        sess = acct_session(rec)                   # [BAPATCH-MULTIACCT v1] 本请求那个账号的桶
        sk = getattr(sess, 'session_key', None) or {}
        if isinstance(sk, dict) and sk.get('AccountServerId'):
            return int(sk['AccountServerId'])
        aid = getattr(sess, 'account_id', None)
        if aid:
            return int(aid)
    except Exception:
        pass
    if isinstance(rec, dict):
        for k in ('acct_server_id', 'req_AccountServerId'):
            v = rec.get(k)
            if v:
                try:
                    return int(v)
                except Exception:
                    pass
    return P3_DEFAULT_ACCOUNT


def p3_mxtoken(account_id):
    """由账号派生 64 字符 base64 MxToken（sha384 48 字节，与 gen_common.Account 同一公式）。"""
    raw = _p3hashlib.sha384(
        ('ba-private-server:%d' % int(account_id)).encode('utf-8')).digest()
    return _p3base64.b64encode(raw).decode('ascii')


def p3_requestid(rec=None):
    """外层 requestid / 内层 RequestId 用同一个值（官方逐字节相同）。"""
    rid = None
    fn = globals().get('pick_requestid')
    if callable(fn):
        try:
            rid = fn(rec if isinstance(rec, dict) else {})
        except Exception:
            rid = None
    if not rid:
        rid = str(_p3uuid.uuid4())
    return rid


# ---------------------------------------------------------------- 载荷
def p3_build(account_id, mxtoken, request_id, ticks, server_ticks=None):
    """7 键官方结构。

    ReceiveTick == EchoSendTick == ticks  —— 红线：绝不能是 0（客户端靠它算时钟偏移）。
    ServerTimeTicks = server_ticks（不给就同 ticks）。官方 ServerTimeTicks 比两个 tick 大
    12 ticks（1.2 µs）：那是「收到请求」和「组包发出」两次取时之差，运行时按两次采样给。
    """
    ticks = int(ticks)
    stt = ticks if server_ticks is None else int(server_ticks)
    if stt < ticks:
        stt = ticks
    obj = {
        'Protocol': P3_PROTOCOL,
        'SessionKey': {'AccountServerId': int(account_id), 'MxToken': mxtoken},
        'ServerTimeTicks': stt,
        'ServerNotification': 0,
        'RequestId': request_id,
        'ReceiveTick': ticks,
        'EchoSendTick': ticks,
    }
    return dict((k, obj[k]) for k in P3_ORDER if k in obj)


def p3_inner_len(obj):
    return len(json_dumps_compact(obj))


def json_dumps_compact(obj):
    import json as _j
    return _j.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def p3_route(rec, name=None, num=None, frag=None, send=None, base=None, hook=None):
    """协议 3 的接管线。返回 (200, wire, ctype)；不管 -> None（交回原有兜底）。

    send 必须注入（bridge 传 cn_wire.wrap_response，测试可传替身）：
        send(protocol_name, inner_obj, requestid) -> (wire, plain, key)
    任何异常都往上抛，由 hook 的 try/except 兜住并记 rec['p3_err']。
    """
    proto = p3_num(num, name)
    if proto is None:
        return None
    if not p3_switch_on(base):
        if isinstance(rec, dict):
            rec['p3_off'] = proto
        return None
    if send is None:
        return None

    if isinstance(rec, dict) and isinstance(frag, str) and frag:
        rec['p3_frag_head'] = frag[:200]

    sid_frag, mx_frag = p3_session_from_frag(frag)
    account_id = p3_account_id(rec, frag)
    mxtoken = mx_frag or p3_mxtoken(account_id)
    mode = p3_ticks_mode(base)
    ticks = p3_ticks(p3_now(mode), mode)                 # 收到请求那一刻 -> 两个 tick
    server_ticks = p3_ticks(p3_now(mode), mode)          # 组包那一刻 -> ServerTimeTicks
    rid = p3_requestid(rec)

    obj = p3_build(account_id, mxtoken, rid, ticks, server_ticks=server_ticks)
    wire, plain, key = send(P3_NAME, obj, rid)

    if isinstance(rec, dict):
        rec['gen_kind'] = 'networktime-3'
        rec['p3_hook'] = hook or '?'
        rec['p3_proto'] = proto
        rec['p3_name'] = P3_NAME
        rec['p3_account_id'] = account_id
        rec['p3_session_from_request'] = bool(sid_frag or mx_frag)
        rec['p3_ticks_mode'] = mode
        rec['p3_ticks'] = int(ticks)
        rec['p3_server_ticks'] = obj['ServerTimeTicks']
        rec['p3_server_tick_delta'] = obj['ServerTimeTicks'] - obj['ReceiveTick']
        rec['p3_receive_tick'] = obj['ReceiveTick']
        rec['p3_echo_tick'] = obj['EchoSendTick']
        rec['p3_tick_delta'] = obj['EchoSendTick'] - obj['ReceiveTick']
        rec['p3_requestid_echo'] = (obj.get('RequestId') == rid)
        rec['p3_keys'] = len(obj)
        rec['enc_requestid'] = rid
        rec['enc_inner_keys'] = len(obj)
        rec['enc_plain_len'] = len(plain)
        rec['enc_body_len'] = len(wire)
        rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
    return 200, wire, 'text/plain; charset=utf-8'
# <<< BAPATCH-P3-PAYLOAD v1 END <<<
# >>> BAPATCH-RELAY-PAYLOAD v1 BEGIN >>> (deploy/patch_relay.py 内嵌 RL_PAYLOAD_SRC，sha256=8db678f98cf18e39fca2e9fbde49838edf85f4b92e8053a3608346deb720b5a2) >>>
# -*- coding: utf-8 -*-
"""未知协议 -> 本地 Shittim 转发（bridge 运行时真源，patch_relay.py --verify 逐字节比对）。

问题：_bridge() 的 `if name is None:` 分支先调 _generic_protocol_response()，它只回
     {"Protocol":<num>, "ServerTimeTicks":…, "ServerNotification":0, …} 的 min+base
     空壳，不会把客户端真实请求送去 Shittim。8000 / 8006 / 90011 / 35003 / 16000 卡在这里。

做法（开关打开时）：
     ① cn_cipher.decode_packet(packet_b64, proto_str) 解出客户端真实请求；
     ② ensure_session(rec) 打 Account_CheckNexon(1014) 拿真 SessionKey 并注入；
     ③ post_gateway(req) POST 到本地 Shittim 的 /api/gateway；
     ④ unwrap_gateway_response(raw) 拿 dict；
     ⑤ bridge 自己的 _cn_envelope(proto_str, obj, rec) 包成 CN 信封返回。
     任何一步不成就 return None，原逻辑（min+base / forward）照旧，绝不 500。

红线：
  * RL_HANDLED 里的协议号（3/1005/1017/1019/24000/26000/4000/90004）**显式排除**。
    本机 protocol_names.txt 缺失时 24000 / 90004 的 name 也是 None，没有这张表，
    开关一开就会把它们从真生成器手里抢走。
  * Account_CheckNexon(1014) 在名字表里，结构上到不了本分支；RL_LOCAL.busy 再挡
    一层同线程重入（嵌套调用直接落回原逻辑，不死循环）。
  * 开关缺失/0 => 完全不改行为（fail-safe）。

开关查找顺序（与 p3_read_file / simple_read_switch 一致）：
    bridge 所在目录 -> /www/wwwroot/bapatch/tools -> /www/wwwroot/bapatch

日志字段（写进 rec）：relay_on / relay_used / relay_code / relay_resp_len /
    relay_protocol / relay_err / relay_fallthrough
  辅助：relay_protocol_num / relay_num / relay_frag_len / relay_shittim_keys /
    relay_session_injected / relay_gateway_protocol / relay_account_id

约定（原样贴进 bridge 模块命名空间）：
  * 不写 from __future__，不写 __main__ 块；
  * 只用标准库，全部用 _rl* 别名 import，不污染 bridge 现有全局名；
  * import 期不碰文件系统、不碰网络；bridge 依赖一律 globals().get() 运行时取。
"""
import json as _rljson
import os as _rlos
import re as _rlre
import threading as _rlthreading

RL_SWITCH_FILE = 'cn_relay_unknown.txt'
RL_FALLBACK_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')
# 有真生成器 / 别的 hook 负责的协议号：本 hook 一律不碰（名字表缺名字时尤其重要）
RL_HANDLED = frozenset((3, 1005, 1017, 1019, 24000, 26000, 4000, 90004))
RL_SKIP_NAMES = frozenset(('Account_CheckNexon',))
RL_LOCAL = _rlthreading.local()


# ---------------------------------------------------------------- 开关
def rl_dirs():
    """开关文件的候选目录（有序）。"""
    out = []
    try:
        out.append(_rlos.path.dirname(_rlos.path.abspath(__file__)))
    except Exception:
        pass
    for d in RL_FALLBACK_DIRS:
        if d not in out:
            out.append(d)
    return out


def rl_read_file(fn, base=None):
    """读一个小开关文件 -> (路径, 内容)。找不到 -> (None, None)。"""
    dirs = ([base] if base else []) + rl_dirs()
    for d in dirs:
        if not d:
            continue
        p = _rlos.path.join(d, fn)
        try:
            with open(p, 'r') as fh:
                return p, fh.read().strip()
        except Exception:
            continue
    return None, None


def rl_switch_on(base=None):
    """未知协议转发是否启用。缺失 / 读不到 / 内容不是真值 -> False（fail-safe）。"""
    _p, v = rl_read_file(RL_SWITCH_FILE, base)
    if v is None:
        return False
    return v.strip().lower() in ('1', 'on', 'true', 'yes')


# ---------------------------------------------------------------- 请求重建
def rl_num_from_frag(frag):
    """协议号 = 请求里 Hash 的高 32 位（客户端每个请求都自带 Hash）。"""
    if not isinstance(frag, str) or not frag:
        return None
    m = _rlre.search(r'"Hash"\s*:\s*(\d+)', frag)
    if not m:
        return None
    try:
        return int(m.group(1)) >> 32
    except Exception:
        return None


# >>> BAPATCH-RLFIX v1 BEGIN >>> (deploy/patch_relay_fix.py 内嵌 RLFIX_HELPER_SRC，sha256=ccdc3780246a93998bced42cf28d7473ed9a277bf47feda98450617e21217986) >>>
# -*- coding: utf-8 -*-
"""BAPATCH-RLFIX v1：relay 运行时修正（协议号拼接 / 会话失效重试）。

被 patch_relay_fix.py 插在 patch_relay.py 的 RL_PAYLOAD 里（rl_request_json 之前），
relay v1（cn_relay_unknown.txt）与 relay2（cn_relay_known.txt）两条转发路径共用。

* _rl_build_request(num, text, rec)：
  decode_packet 解出的 fragment 偶尔以协议号最后一位数字开头（19004 -> "4,…"），
  原逻辑 '{"Protocol":19004' + "4,…" 会拼成 190044。这里按候选顺序试，只有
  json.loads 成功、Protocol == num、且不是空 dict 才接受；全部不成立 -> None。
* _rl_is_auth_fail(obj)：识别 Shittim 的鉴权失败信封。
* _rl_retry_on_auth_fail(...)：清桥会话缓存（同一把 SESSION.lock）-> 重新
  ensure_session -> 重新 post_gateway，只重试一次。

日志字段：rl_req_build / rl_req_frag_head / rl_req_build_err /
          rl_session_retry / rl_session_retry_ok。
"""
RLFIX_FRAG_DROP_MAX = 8


def _rl_frag_candidates(num, text):
    """按候选顺序给出 (候选号, 要丢给 json.loads 的文本)。

    1     原逻辑：'{"Protocol":<num>' + text
    2     text[0] 是数字：从第一个逗号处截断后再拼
    3-10  依次去掉开头 1..8 个字符，再从第一个逗号处截断后拼
    11    text 以 } / , 之外的可疑字符开头：同样从第一个逗号处截断

    没有逗号可截的候选直接跳过（拼不出合法 JSON）。重复文本不剔除：先命中的
    候选号就是 rec['rl_req_build']，顺序本身就是可核对的事实。
    """
    n = int(num)
    cands = [(1, '{"Protocol":%d' % n + text)]
    comma = text.find(',')
    if text[:1].isdigit() and comma >= 0:
        cands.append((2, '{"Protocol":%d' % n + text[comma:]))
    for k in range(1, RLFIX_FRAG_DROP_MAX + 1):
        rest = text[k:]
        c = rest.find(',')
        if c >= 0:
            cands.append((2 + k, '{"Protocol":%d' % n + rest[c:]))
    if text[:1] and text[0] not in ('}', ',') and comma >= 0:
        cands.append((3 + RLFIX_FRAG_DROP_MAX, '{"Protocol":%d' % n + text[comma:]))
    return cands


def _rl_build_request(num, text, rec=None):
    """fragment -> 可发给 Shittim 的请求 dict；所有候选都不成立 -> None（不猜）。"""
    if isinstance(rec, dict):
        rec['rl_req_frag_head'] = text[:200]
        rec['rl_req_build'] = 0
        rec['rl_req_build_err'] = ''
    try:
        n = int(num)
    except Exception as e:
        if isinstance(rec, dict):
            rec['rl_req_build_err'] = 'bad num: %r' % (e,)
        return None
    errs = []
    for cid, body in _rl_frag_candidates(n, text):
        try:
            obj = _rljson.loads(body)
        except Exception as e:
            if len(errs) < 4:
                errs.append('c%d:%s' % (cid, type(e).__name__))
            continue
        if not isinstance(obj, dict) or not obj:
            if len(errs) < 4:
                errs.append('c%d:not-dict-or-empty' % cid)
            continue
        if obj.get('Protocol') != n:
            if len(errs) < 4:
                errs.append('c%d:Protocol=%r' % (cid, obj.get('Protocol')))
            continue
        if isinstance(rec, dict):
            rec['rl_req_build'] = cid
            rec['rl_req_build_err'] = ''
        return obj
    if isinstance(rec, dict):
        rec['rl_req_build_err'] = ('all candidates failed (%d tries): %s'
                                   % (len(errs), '; '.join(errs)))[:300]
    return None


def _rl_is_auth_fail(obj):
    """Shittim 的「Session expired or invalid」是否打回来了。"""
    if not isinstance(obj, dict):
        return False
    if obj.get('Protocol') == -1:
        return True
    ec = obj.get('ErrorCode')
    if isinstance(ec, int) and ec != 0:
        return True
    msg = str(obj.get('Msg') or obj.get('Message') or '')
    return 'Session' in msg and ('expired' in msg.lower() or 'invalid' in msg.lower())


def _rl_clear_session(rec=None):
    """清桥缓存的 session_key / account_id（同一把 SESSION.lock）；失败不抛。

    [BAPATCH-MULTIACCT v1] 清的是"本请求那个账号"的桶（每桶自己的锁）；开关关时
    acct_session() 返回基线单例，行为与原来逐字一致 —— 绝不清别人的会话。
    """
    sess = None
    try:
        sess = acct_session(rec)
    except Exception:
        sess = None
    if sess is None:
        sess = globals().get('SESSION')
    if sess is None:
        return False
    try:
        lock = getattr(sess, 'lock', None)
        if lock is not None:
            with lock:
                sess.session_key = None
                sess.account_id = None
        else:
            sess.session_key = None
            sess.account_id = None
    except Exception as e:
        if isinstance(rec, dict):
            rec['rl_session_clear_err'] = repr(e)
        return False
    return True


def _rl_retry_on_auth_fail(rec, req, post, unwrap, ensure, timeout=None,
                           family=None, log=None):
    """鉴权失败后的唯一一次重试：清缓存 -> ensure_session -> post_gateway。

    成功 -> (code, raw, gp, obj)；失败 / 异常 -> None（调用方落回原逻辑，不 500）。
    日志：rl_session_retry=True / rl_session_retry_ok=True|False。
    """
    if not isinstance(rec, dict):
        return None
    if rec.get('rl_session_retry'):
        # 只重试一次：同一个 rec 已经重试过就直接放弃
        return None
    rec['rl_session_retry'] = True
    rec['rl_session_retry_ok'] = False
    try:
        _rl_clear_session(rec)
        sk, _aid = ensure(rec)
        if sk is None:
            rec['rl_session_retry_err'] = 'ensure_session returned None'
            return None
        # BAPATCH-RLFIX2: 重试也走无条件覆盖（不是「缺了才补」），并留 overwrote/old_sid
        _rlfix2_force_session(rec, req, sk, family, log)
        if timeout is None:
            code, raw = post(req)
        else:
            try:
                code, raw = post(req, timeout=timeout)
            except TypeError:
                # 变体 bridge 的 post_gateway 可能没有 timeout 形参
                code, raw = post(req)
        raw = raw or b''
        if code == 0:
            rec['rl_session_retry_err'] = 'gateway unreachable/timeout'
            return None
        gp, obj = unwrap(raw)
        if not isinstance(obj, dict) or _rl_is_auth_fail(obj):
            rec['rl_session_retry_err'] = 'still auth-failed'
            return None
        rec['rl_session_retry_ok'] = True
        return code, raw, gp, obj
    except Exception as e:
        rec['rl_session_retry_err'] = repr(e)
        return None
# >>> BAPATCH-RLFIX2 v1 BEGIN >>> (deploy/patch_relay_fix2.py 内嵌 RLFIX2_HELPER_SRC，sha256=9391eb244263eb91d51b2fd924da94f232b3421b0b394d13e12717a8af27be56) >>>
# -*- coding: utf-8 -*-
"""BAPATCH-RLFIX2 v1：relay 转发时**无条件**用桥铸的 SessionKey 覆盖请求。

被 patch_relay_fix2.py 插在 patch_relay_fix v1 的 RLFIX 块之后（rl_request_json 之前），
relay v1（cn_relay_unknown.txt）与 relay2（cn_relay_known.txt）两条转发路径
以及 relayfix 的 session-retry 三处入口共用这一份实现。

问题：桥账号服务把 SessionKey.AccountServerId 改成 10000000001，客户端回传它；
relay 原来的「缺了才注入」因此跳过注入 -> Shittim 收到不存在的账号 id -> 拒。

* _rlfix2_session_family(rec, timeout)：判当前属于哪条 relay（relay1 / relay2）。
* _rlfix2_force_session(rec, req, sk, family, log)：无条件覆盖 req['SessionKey']。
  sk is None -> 不覆盖、返回 False（调用方落回，保持打补丁前行为，不 500）。

日志：<family>_session_injected / <family>_session_overwrote / <family>_session_old_sid
      以及本补丁新增的 <log>_session_overwrote / <log>_session_old_sid。
"""


def _rlfix2_session_family(rec=None, timeout=None):
    """当前转发/重试属于哪条 relay -> (字段家族, 日志前缀)。

    判定顺序（先看最确定的信号）：
      1. timeout 非 None —— 只有 relay2 会带 RL2_TIMEOUT 调 post，最可靠；
      2. rec['relay2_on'] / rec['relay2_num'] 有、且没有 relay v1 的对应标记；
      3. 其余一律当 relay v1（rl_route 之前的默认路径）。
    """
    if timeout is not None:
        return 'relay2', 'rl2'
    if isinstance(rec, dict):
        is2 = rec.get('relay2_on') is True or rec.get('relay2_num') is not None
        is1 = rec.get('relay_on') is True or rec.get('relay_num') is not None
        if is2 and not is1:
            return 'relay2', 'rl2'
    return 'relay', 'rl'


def _rlfix2_force_session(rec, req, sk, family=None, log=None):
    """无条件用桥铸的 sk 覆盖 req['SessionKey']；返回 True 表示已覆盖。

    * 不看请求里原来有没有 SessionKey：客户端带来的（错的）一律覆盖。
    * sk is None -> 不动请求、返回 False（调用方落回原逻辑，不 500）。
    * 日志：
        <family>_session_injected  是否已用桥的 sk 填进去（True）
        <family>_session_overwrote 是否真的改了（原来有值且不相等）
        <family>_session_old_sid   被覆盖掉的那个 AccountServerId（没有则 None）
        <log>_session_overwrote / <log>_session_old_sid  同一份事实的短名
    """
    if not isinstance(req, dict):
        return False
    if family is None or log is None:
        _fam, _log = _rlfix2_session_family(rec)
        family = family or _fam
        log = log or _log
    if sk is None:
        if isinstance(rec, dict):
            rec[family + '_session_injected'] = False
        return False
    try:
        old = req.get('SessionKey')
    except Exception:
        old = None
    try:
        same = (old == sk)
    except Exception:
        same = False
    req['SessionKey'] = sk
    if isinstance(rec, dict):
        over = (old is not None and not same)
        try:
            old_sid = old.get('AccountServerId') if isinstance(old, dict) else old
        except Exception:
            old_sid = None
        rec[family + '_session_injected'] = True
        rec[family + '_session_overwrote'] = over
        rec[family + '_session_old_sid'] = old_sid
        rec[log + '_session_overwrote'] = over
        rec[log + '_session_old_sid'] = old_sid
    return True
# <<< BAPATCH-RLFIX2 v1 END <<<
# <<< BAPATCH-RLFIX v1 END <<<
def rl_request_json(decoded, rec=None):
    """cn_cipher.decode_packet() 的结果 -> 可发给 Shittim 的请求 dict；失败 -> None。

    decode_packet 的 'json' 只在它认识 protocol token 时才填（参照实现
    report/_tmp/mx_crypto/cn_cipher.py 的 PROTOCOL_MAP 只有 Account_Auth 一条）；
    而本 hook 面对的正是「名字表里没有」的 token，所以 'json' 常常是 None。
    这时用 'fragment'（客户端明文片段，形如 ',"Hash":…,"IsTest":false}'）拼回
    完整请求：'{"Protocol":<num>' + fragment。Protocol 用数字，交给 Shittim 的
    enum 反序列化（它本来就接受数字与名字两种写法）。
    """
    if not isinstance(decoded, dict):
        return None
    js = decoded.get('json')
    if isinstance(js, dict) and js:
        return js
    frag = decoded.get('fragment')
    if not isinstance(frag, str):
        return None
    text = frag.strip()
    if not text:
        return None
    # BAPATCH-RLFIX: 请求片段头落进访问日志（上层已写则不覆盖）
    try:
        _FRAG_TLS.v = text if isinstance(text, str) else None
        _FRAG_TLS.seq = _req_seq(rec)          # [修 3] 单调序号，替代 id(rec)（地址会被复用）
    except Exception:
        _FRAG_TLS.v = None
        _FRAG_TLS.seq = None
    if isinstance(rec, dict) and not rec.get('req_frag_head'):
        rec['req_frag_head'] = mask_secret(text[:300])
    if text[0] == '{':
        try:
            obj = _rljson.loads(text)
        except Exception:
            return None
        return obj if isinstance(obj, dict) else None
    num = rl_num_from_frag(text)
    if num is None and isinstance(rec, dict):
        h = rec.get('req_Hash')
        if isinstance(h, int) and h > 0:
            num = h >> 32
    if num is None:
        return None
    # BAPATCH-RLFIX: 统一走 _rl_build_request（候选顺序 + Protocol 硬校验；全失败 -> None）
    return _rl_build_request(num, text, rec)


def rl_num_from_request(decoded, req=None):
    """协议号：片段 Hash>>32 -> 请求 JSON 的 Hash >>32 -> 请求 JSON 的 Protocol(int)。"""
    num = None
    if isinstance(decoded, dict):
        num = rl_num_from_frag(decoded.get('fragment'))
    if num is None and isinstance(req, dict):
        h = req.get('Hash')
        if isinstance(h, int) and h > 0:
            num = h >> 32
        elif isinstance(h, str) and h.strip().isdigit():
            num = int(h.strip()) >> 32
    if num is None and isinstance(req, dict):
        p = req.get('Protocol')
        if isinstance(p, int) and p > 0:
            num = p
    return num


# ---------------------------------------------------------------- 转发管线
def rl_route(rec, proto_str, packet_b64, name=None, envelope=None, base=None):
    """未知协议的接管线。已接管 -> (code, body, ctype)；不管 -> None（交回原兜底）。

    envelope 必须注入（bridge 传 self._cn_envelope）：
        envelope(proto_str, inner_obj, rec) -> (code, body, ctype)
    任何异常都不在这里吞：由 HOOK-A 的 try/except 兜住并记 rec['relay_err']。
    """
    if not isinstance(rec, dict):
        rec = {}
    on = bool(rl_switch_on(base))
    rec['relay_on'] = on
    rec['relay_err'] = ''
    if not on:
        rec['relay_fallthrough'] = 'switch-off'
        return None
    if isinstance(name, str) and name and name != 'Unknown':
        rec['relay_fallthrough'] = 'known-name'
        return None
    if isinstance(name, str) and name in RL_SKIP_NAMES:
        rec['relay_fallthrough'] = 'skip-name'
        return None
    if getattr(RL_LOCAL, 'busy', False):
        rec['relay_fallthrough'] = 'reentrant'
        return None
    RL_LOCAL.busy = True
    try:
        return _rl_relay_once(rec, proto_str, packet_b64, envelope)
    finally:
        RL_LOCAL.busy = False


def _rl_relay_once(rec, proto_str, packet_b64, envelope):
    """真正干活的只有这一段；异常往上抛（HOOK-A 负责留痕 + 落回）。"""
    dec = globals().get('cn_cipher')
    if dec is None or not hasattr(dec, 'decode_packet'):
        rec['relay_err'] = 'cn_cipher.decode_packet unavailable'
        rec['relay_fallthrough'] = 'no-cn_cipher'
        return None
    try:
        decoded = dec.decode_packet(packet_b64, proto_str)
    except Exception as e:
        rec['relay_err'] = repr(e)
        rec['relay_fallthrough'] = 'decode'
        return None
    # BAPATCH-RLFIX: decode 结果里的 fragment 头部落日志（上层已写则不覆盖）
    _frag = decoded.get('fragment') if isinstance(decoded, dict) else None
    try:
        _FRAG_TLS.v = _frag if isinstance(_frag, str) else None
        _FRAG_TLS.seq = _req_seq(rec)          # [修 3] 单调序号，替代 id(rec)（地址会被复用）
    except Exception:
        _FRAG_TLS.v = None
        _FRAG_TLS.seq = None
    if isinstance(rec, dict) and not rec.get('req_frag_head'):
        if isinstance(_frag, str):
            rec['req_frag_head'] = mask_secret(_frag[:300])
    req = rl_request_json(decoded, rec)
    if not isinstance(req, dict):
        rec['relay_fallthrough'] = 'decode-json'
        return None
    rec['relay_frag_len'] = len(decoded.get('fragment') or '') if isinstance(decoded, dict) else 0
    num = rl_num_from_request(decoded, req)
    rec['relay_num'] = num
    if num is None:
        rec['relay_fallthrough'] = 'no-protocol-num'
        return None
    if num in RL_HANDLED:
        # 3/1005/1017/1019/24000/26000/4000/90004 有真生成器：绝不抢
        rec['relay_fallthrough'] = 'handled-%d' % num
        return None
    ensure = globals().get('ensure_session')
    post = globals().get('post_gateway')
    unwrap = globals().get('unwrap_gateway_response')
    if not (callable(ensure) and callable(post) and callable(unwrap)):
        rec['relay_err'] = ('bridge deps missing: ensure_session=%r post_gateway=%r '
                            'unwrap_gateway_response=%r'
                            % (callable(ensure), callable(post), callable(unwrap)))
        rec['relay_fallthrough'] = 'no-deps'
        return None
    sk, aid = ensure(rec)
    # BAPATCH-RLFIX2: sk 为 None -> 不覆盖、直接落回（保持打补丁前行为，不 500）
    if sk is None:
        rec['relay_fallthrough'] = 'ensure-session'
        return None
    # BAPATCH-RLFIX2: 无条件用桥铸的 sk 覆盖（客户端回传的是桥账号服务的 SessionKey）
    _rlfix2_force_session(rec, req, sk, 'relay', 'rl')
    rec['relay_account_id'] = aid
    code, raw = post(req)
    raw = raw or b''
    rec['relay_code'] = code
    rec['relay_resp_len'] = len(raw)
    if code == 0:
        rec['relay_err'] = 'gateway unreachable/timeout: %r' % (raw[:160],)
        rec['relay_fallthrough'] = 'gateway-code-0'
        return None
    gp, obj = unwrap(raw)
    if isinstance(gp, (str, int)) or gp is None:
        rec['relay_gateway_protocol'] = gp
    else:
        rec['relay_gateway_protocol'] = repr(gp)
    if not isinstance(obj, dict):
        rec['relay_err'] = ('shittim response not dict (code=%r len=%d body=%r)'
                            % (code, len(raw), raw[:160]))
        rec['relay_fallthrough'] = 'shittim-non-dict'
        return None
    # BAPATCH-RLFIX: Shittim 判定 Session expired/invalid -> 清桥缓存后只重试一次
    if _rl_is_auth_fail(obj):
        _rlfix_got = _rl_retry_on_auth_fail(rec, req, post, unwrap, ensure)
        if _rlfix_got is None:
            rec['relay_fallthrough'] = 'session-retry-failed'
            return None
        code, raw, gp, obj = _rlfix_got
        rec['relay_code'] = code
        rec['relay_resp_len'] = len(raw)
        rec['relay_session_injected'] = True
        if isinstance(gp, (str, int)) or gp is None:
            rec['relay_gateway_protocol'] = gp
        else:
            rec['relay_gateway_protocol'] = repr(gp)
    rec['relay_protocol'] = req.get('Protocol') if req.get('Protocol') is not None else num
    rec['relay_protocol_num'] = num
    if isinstance(obj.get('Protocol'), int):
        rec['relay_shittim_protocol'] = obj.get('Protocol')
    rec['relay_shittim_keys'] = len(obj)
    out = None
    if callable(envelope):
        out = envelope(proto_str, obj, rec)
    if out is None:
        rec['relay_fallthrough'] = 'envelope'
        return None
    rec['relay_used'] = True
    rec['relay_fallthrough'] = ''
    return out
# <<< BAPATCH-RELAY-PAYLOAD v1 END <<<
# >>> BAPATCH-RELAY2-PAYLOAD v1 BEGIN >>> (deploy/patch_relay2.py 内嵌 RL2_PAYLOAD_SRC，sha256=cab63ac0e9c6e7440d6879dfda56df040385b821c76417ed38945df14532c32d) >>>
# -*- coding: utf-8 -*-
"""名字已知但没有真生成器的协议 -> 本地 Shittim 转发（bridge 运行时真源）。

为什么要这一版：patch_relay.py 的 HOOK-A 挂在 `if name is None:` 分支里，只对「名字表里
查不到」的协议生效。但 protocol_names.txt 里 Mission_List(8000) / Account_SetTutorial(1006)
这些名字都在，所以它们进不了那个分支，只能拿到 min+base 空壳。本模块的钩子挂在
`if proto_int:` **之前**（与它同级、都在 `_bridge` 的语句序列里），名字已知也照样接管。

做法（开关 cn_relay_known.txt 打开时）：
  ① cn_cipher.decode_packet(packet_b64, proto_str) 解出客户端真实请求（与 HOOK-A 同一个解码器）；
  ② 复用 relay v1 的 RL_PAYLOAD 里已经验证过的 rl_request_json / rl_num_from_request
     拼回发给 Shittim 的请求、取出协议号 —— 不另写一套；
  ③ ensure_session(rec) 打 Account_CheckNexon(1014) 拿真 SessionKey（缺才注入）；
  ④ post_gateway(req, timeout=8) POST 到本地 Shittim 的 /api/gateway。
     8 秒而不是默认 40 秒：这条路径每个请求都要走，40 秒会把客户端拖到超时；
  ⑤ unwrap_gateway_response(raw) -> dict 就用 self._cn_envelope(协议名, obj, rec) 返回。
     （传协议名不是 token：_cn_envelope 内部会算 base32(md5(名字))，那正好等于客户端
      请求里带的 token；传 token 会二次哈希，外层 protocol 就对不上了。）
  任何一步不成就 return None，原逻辑（if proto_int 的 min-envelope / min+base / forward）
  照旧，绝不 500。

红线：
  * RL2_HANDLED（1002/1014/1000/1009/1012/1019/2001/3/1005/1017/24000/26000/4000/90004）
    一律不碰：要么在更前面的分支已经 return（结构上到不了这里），要么有真生成器
    （24000 / 1017 / 90004 在 _generic_protocol_response 里）。排除表是双保险。
  * Account_CheckNexon 名字级排除 + RL2_LOCAL.busy 同线程重入保护：ensure_session 内部
    那次 1014 直接走 post_gateway、不经过 bridge，嵌套调用也被挡住，不会递归。
  * 开关缺失 / 不是真值 => 完全不改行为（fail-safe）。

依赖（运行时从 bridge 全局取，取不到就落回，不抛）：
    cn_cipher.decode_packet / ensure_session / post_gateway / unwrap_gateway_response
    rl_request_json / rl_num_from_request / rl_read_file（= patch_relay.py 的 RL_PAYLOAD）

开关查找顺序（委托 rl_read_file，与 patch_3 / patch_relay 一致）：
    bridge 所在目录 -> /www/wwwroot/bapatch/tools -> /www/wwwroot/bapatch

日志字段（写进 rec）：
    relay2_on / relay2_used / relay2_code / relay2_resp_len / relay2_protocol /
    relay2_err / relay2_fallthrough
  辅助：relay2_num / relay2_name / relay2_session_injected / relay2_account_id /
    relay2_gateway_protocol / relay2_shittim_protocol / relay2_shittim_keys

约定（原样贴进 bridge 模块命名空间）：
  * 不写 from __future__，不写 __main__ 块；
  * 只用标准库，全部 _rl2* 别名 import，不污染 bridge 现有全局名；
  * import 期不碰文件系统、不碰网络；bridge 依赖一律 globals().get() 运行时取。
"""
import os as _rl2os
import threading as _rl2threading

RL2_VER = 'v1'
RL2_SWITCH_FILE = 'cn_relay_known.txt'
RL2_FALLBACK_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')
# 转发超时：这条路径每个请求都走，必须短（默认 40 秒会让客户端超时）
RL2_TIMEOUT = 8
# 有真生成器 / 更前面的专分支负责的协议号：本 hook 一律不碰（双保险）
RL2_HANDLED = frozenset((1002, 1014, 1000, 1009, 1012, 1019, 2001, 3, 1017,   # FIX-2: 1005 已移出，改走转发
                         24000, 26000, 90004,   # ITEMLIST-4000 v2: 4000 移出排除表，改走 relay2
                         90011))   # BAPATCH-90011 v1: Shop_ListTutorialGacha (no Shittim enum/handler)
RL2_SKIP_NAMES = frozenset(('Account_CheckNexon', 'Account_Auth', 'Account_Auth2',
                            'Account_LoginSync', 'Account_Nickname', 'Account_CallName'))
RL2_LOCAL = _rl2threading.local()


# ---------------------------------------------------------------- 开关
def rl2_dirs():
    """开关文件的候选目录（有序）：bridge 目录 -> bapatch/tools -> bapatch。"""
    out = []
    try:
        out.append(_rl2os.path.dirname(_rl2os.path.abspath(__file__)))
    except Exception:
        pass
    for d in RL2_FALLBACK_DIRS:
        if d not in out:
            out.append(d)
    return out


def rl2_read_file(fn, base=None):
    """读一个小开关文件 -> (路径, 内容)。优先复用 relay v1 的 rl_read_file。"""
    rd = globals().get('rl_read_file')
    if callable(rd):
        try:
            return rd(fn, base)
        except Exception:
            pass
    dirs = ([base] if base else []) + rl2_dirs()
    for d in dirs:
        if not d:
            continue
        p = _rl2os.path.join(d, fn)
        try:
            with open(p, 'r') as fh:
                return p, fh.read().strip()
        except Exception:
            continue
    return None, None


def rl2_switch_on(base=None):
    """cn_relay_known.txt 是否打开。缺失 / 读不到 / 内容不是真值 -> False（fail-safe）。"""
    _p, v = rl2_read_file(RL2_SWITCH_FILE, base)
    if v is None:
        return False
    return v.strip().lower() in ('1', 'on', 'true', 'yes')


# ---------------------------------------------------------------- 转发管线
def rl2_route(rec, proto_str, packet_b64, name=None, envelope=None, base=None):
    """名字已知（但没有真生成器）的协议接管线。接管 -> (code, body, ctype)；不管 -> None。

    envelope 必须注入（bridge 传 self._cn_envelope）：
        envelope(协议名, inner_obj, rec) -> (code, body, ctype)
      （传**协议名**不是客户端 token：_cn_envelope 内部算 base32(md5(名字))，那才等于
        客户端请求里带的 token；传 token 会二次哈希。）
    任何异常都不在这里吞：由 HOOK 的 try/except 兜住并记 rec['relay2_err']。
    """
    if not isinstance(rec, dict):
        rec = {}
    on = bool(rl2_switch_on(base))
    rec['relay2_on'] = on
    rec['relay2_err'] = ''
    if not on:
        rec['relay2_fallthrough'] = 'switch-off'
        return None
    if isinstance(name, str) and name in RL2_SKIP_NAMES:
        # BAPATCH-1017RELAY v1: LoginSync 开关打开时不吃 skip
        if (name == RELAY1017_NAME and relay1017_on()):
            rec['relay1017_skip_bypass'] = True
        else:
            rec['relay2_fallthrough'] = 'skip-name'
            return None
    if getattr(RL2_LOCAL, 'busy', False):
        rec['relay2_fallthrough'] = 'reentrant'
        return None
    RL2_LOCAL.busy = True
    try:
        return _rl2_relay_once(rec, proto_str, packet_b64, name, envelope)
    finally:
        RL2_LOCAL.busy = False


def _rl2_relay_once(rec, proto_str, packet_b64, name, envelope):
    """真正干活的只有这一段；异常往上抛（HOOK 负责留痕 + 落回）。"""
    dec = globals().get('cn_cipher')
    if dec is None or not hasattr(dec, 'decode_packet'):
        rec['relay2_err'] = 'cn_cipher.decode_packet unavailable'
        rec['relay2_fallthrough'] = 'no-cn_cipher'
        return None
    # 复用 patch_relay.py 的 RL_PAYLOAD：请求重建 / 协议号提取只信这一份实现
    req_builder = globals().get('rl_request_json')
    num_reader = globals().get('rl_num_from_request')
    if not (callable(req_builder) and callable(num_reader)):
        rec['relay2_err'] = ('relay v1 payload missing: rl_request_json=%r '
                             'rl_num_from_request=%r'
                             % (callable(req_builder), callable(num_reader)))
        rec['relay2_fallthrough'] = 'no-relay1'
        return None
    try:
        decoded = dec.decode_packet(packet_b64, proto_str)
    except Exception as e:
        rec['relay2_err'] = repr(e)
        rec['relay2_fallthrough'] = 'decode'
        return None
    # BAPATCH-RLFIX: decode 结果里的 fragment 头部落日志（上层已写则不覆盖）
    _frag = decoded.get('fragment') if isinstance(decoded, dict) else None
    try:
        _FRAG_TLS.v = _frag if isinstance(_frag, str) else None
        _FRAG_TLS.seq = _req_seq(rec)          # [修 3] 单调序号，替代 id(rec)（地址会被复用）
    except Exception:
        _FRAG_TLS.v = None
        _FRAG_TLS.seq = None
    if isinstance(rec, dict) and not rec.get('req_frag_head'):
        if isinstance(_frag, str):
            rec['req_frag_head'] = mask_secret(_frag[:300])
    req = req_builder(decoded, rec)
    if not isinstance(req, dict):
        rec['relay2_fallthrough'] = 'decode-json'
        return None
    num = num_reader(decoded, req)
    rec['relay2_num'] = num
    rec['relay2_name'] = name if isinstance(name, str) else None
    if num is None:
        rec['relay2_fallthrough'] = 'no-protocol-num'
        return None
    # BAPATCH-1017RELAY v1: 协议号对齐 Shittim（1017→1019）
    num = relay1017_fix_num(name, num, req, rec)
    rec['relay2_num'] = num
    if num in RL2_HANDLED:
        # BAPATCH-1017RELAY v1b: LoginSync 开关打开时绕过排除表（1019 在 RL2_HANDLED 里）
        if relay1017_on() and name == RELAY1017_NAME:
            rec['relay1017_handled_bypass'] = True
        else:
            # 1002/1014/3/1005/1017/24000/26000/4000/90004 … 有真生成器或专分支：绝不抢
            rec['relay2_fallthrough'] = 'handled-%d' % num
            return None
    ensure = globals().get('ensure_session')
    post = globals().get('post_gateway')
    unwrap = globals().get('unwrap_gateway_response')
    if not (callable(ensure) and callable(post) and callable(unwrap)):
        rec['relay2_err'] = ('bridge deps missing: ensure_session=%r post_gateway=%r '
                             'unwrap_gateway_response=%r'
                             % (callable(ensure), callable(post), callable(unwrap)))
        rec['relay2_fallthrough'] = 'no-deps'
        return None
    sk, aid = ensure(rec)
    # BAPATCH-RLFIX2: sk 为 None -> 不覆盖、直接落回（保持打补丁前行为，不 500）
    if sk is None:
        rec['relay2_fallthrough'] = 'ensure-session'
        return None
    # BAPATCH-RLFIX2: 无条件用桥铸的 sk 覆盖（同上；本路径用 relay2_ / rl2_ 前缀留痕）
    _rlfix2_force_session(rec, req, sk, 'relay2', 'rl2')
    rec['relay2_account_id'] = aid
    # BAPATCH-DEDUP v1 RELAYPATH: dup order -> replay cached response, never hit Shittim twice
    _dd_k = dedup_key_obj(name, req)
    _dd_hit = dedup_fetch(_dd_k, name, rec)
    if _dd_hit is not None:
        return _dd_hit
    # BAPATCH-1017RELAY v1c: LoginSync 在 Shittim 侧实测 ~9.7s，8s 会超时 -> 单独放宽到 45s
    _to = 45 if (relay1017_on() and name == RELAY1017_NAME) else RL2_TIMEOUT
    rec['relay2_timeout'] = _to
    try:
        code, raw = post(req, timeout=_to)
    except TypeError:
        # 变体 bridge 的 post_gateway 可能没有 timeout 形参：退回默认总比 500 好
        code, raw = post(req)
    raw = raw or b''
    rec['relay2_code'] = code
    rec['relay2_resp_len'] = len(raw)
    if code == 0:
        rec['relay2_err'] = 'gateway unreachable/timeout: %r' % (raw[:160],)
        rec['relay2_fallthrough'] = 'gateway-code-0'
        return None
    gp, obj = unwrap(raw)
    if gp is None or isinstance(gp, (str, int)):
        rec['relay2_gateway_protocol'] = gp
    else:
        rec['relay2_gateway_protocol'] = repr(gp)
    if not isinstance(obj, dict):
        rec['relay2_err'] = ('shittim response not dict (code=%r len=%d body=%r)'
                             % (code, len(raw), raw[:160]))
        rec['relay2_fallthrough'] = 'shittim-non-dict'
        return None
    # BAPATCH-RLFIX: Shittim 判定 Session expired/invalid -> 清桥缓存后只重试一次
    if _rl_is_auth_fail(obj):
        _rlfix_got = _rl_retry_on_auth_fail(rec, req, post, unwrap, ensure,
                                           timeout=RL2_TIMEOUT)
        if _rlfix_got is None:
            rec['relay2_fallthrough'] = 'session-retry-failed'
            return None
        code, raw, gp, obj = _rlfix_got
        rec['relay2_code'] = code
        rec['relay2_resp_len'] = len(raw)
        rec['relay2_session_injected'] = True
        if gp is None or isinstance(gp, (str, int)):
            rec['relay2_gateway_protocol'] = gp
        else:
            rec['relay2_gateway_protocol'] = repr(gp)
    rec['relay2_protocol'] = req.get('Protocol') if req.get('Protocol') is not None else num
    rec['relay2_protocol_num'] = num
    if isinstance(obj.get('Protocol'), int):
        rec['relay2_shittim_protocol'] = obj.get('Protocol')
    rec['relay2_shittim_keys'] = len(obj)
    out = None
    # 注意：bridge 的 _cn_envelope(proto_name, ...) 会自己算 base32(md5(proto_name))，
    # 客户端请求里带的正是 base32(md5(协议名))。所以这里必须传**协议名**，不能传客户端
    # 的 token —— 传 token 会变成 b32md5(b32md5(name))，外层 protocol 就和客户端对不上了。
    proto_name = name if (isinstance(name, str) and name and name != 'Unknown') else proto_str
    rec['relay2_envelope_name'] = proto_name
    if callable(envelope):
        out = envelope(proto_name, obj, rec)
    if out is None:
        rec['relay2_fallthrough'] = 'envelope'
        return None
    rec['relay2_used'] = True
    rec['relay2_fallthrough'] = ''
    # BAPATCH-DEDUP v1 RELAYPATH: cache this response for the dedupe window
    dedup_put(_dd_k, name, out, rec)
    return out
# <<< BAPATCH-RELAY2-PAYLOAD v1 END <<<
if __name__ == '__main__':
    n = load_names()
    print('protocol name table =', n, 'entries')
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(('127.0.0.1', 9097), Handler) as s:
        print('bridge v6 listening on 127.0.0.1:9097 mode=', mode(), 'exp=', exp_flag())
        s.serve_forever()
