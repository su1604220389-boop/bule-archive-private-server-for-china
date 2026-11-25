#!/usr/bin/env python
# -*- coding: utf-8 -*-
u"""account_service.py —— 国服《蔚蓝档案》私服的**多用户账号服务**（纯标准库优先）

它是四层架构里第 ③ 层（数据层）的唯一写入方：把「单用户硬编码 → 每次 auth 都发同一个
AccountDB / 同一个 SessionKey」换成「每个用户独立账号、独立进度、独立会话、持久化」。

对外契约（report/93 §2 逐个说明）：

    identify(req) -> Identity                从 auth 请求体提取 DevId / DeviceUniqueId / Token
    get_or_create_account(identity) -> Account   查库，没有就新建（显式分配 server_id）
    issue_session_key(account) -> SessionKey 生成 MxToken，落库 sessions
    resolve_session(mx_token) -> Account|None 校验会话（大小写不敏感，参考 Shittim OrdinalIgnoreCase）
    load_blob(server_id, kind) -> dict|None  读一个子系统状态块
    save_blob(server_id, kind, payload)      写一个子系统状态块（乐观锁 + 版本号）
    build_account_db_for(account) -> dict    生成 AccountDB 22 字段（时间用无时区 ISO）

另有配套（对接响应构造层要用）：
    build_state_for(account) -> dict         把 accounts 行 + account_blobs 拼回 41 键完整状态
    bootstrap_state(account) -> dict         新账号的初始状态（3 学生 / 28 货币 / 未通关）
    alloc_entity_ids(server_id, n)           实体 id 发号（CharacterDB.ServerId / CafeDBId）
    record_login / revoke_session / log_protocol / stats / delete_account / wipe

用法：
    python account_service.py --selftest                      # 建临时库跑全套自检（必须 exit 0）
    python account_service.py --init-db --db ba.sqlite3        # 建库建表
    python account_service.py --make-template                  # 从 proto/account_state.seeded.json 生成模板
    python account_service.py --stats --db ba.sqlite3
    python account_service.py --dump-state --server-id 10000000000 --out u1.json
    python account_service.py --list-kinds

设计要点（决策与理由见 report/93）：
    D1 server_id 从 10000000000 起（不发小号，避免与真账号量级差 4 个数量级）
    D2 DevId 是主身份键，Token 只做记录（SDK token 会轮换；本地无法验证它）
    D3 每用户 40 个状态块聚成 21 个 blobs，粒度 = 写入事务边界
    D4 会话 30 天 TTL + 每账号默认 1 个活跃会话（顶号对齐 Shittim AddOrUpdate）
    D5 时间字段一律无时区 ISO 字符串，绝不把 datetime 直接塞进 JSON

依赖：仅 sqlite3 + uuid + json（标准库）。MySQL 走可选 pymysql（未安装时 mysql 方言直接报错）。
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import copy
import hashlib
import json
import os
import re
import sqlite3
import sys
import urllib.request
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_SQLITE_PATH = os.path.join(HERE, 'schema_sqlite.sql')
SCHEMA_MYSQL_PATH = os.path.join(HERE, 'schema_mysql.sql')
TEMPLATE_PATH = os.path.join(HERE, 'account_template.json')
PROTO_DIR = os.path.abspath(os.path.join(HERE, os.pardir, 'proto'))
SEEDED_STATE_PATH = os.path.join(PROTO_DIR, 'account_state.seeded.json')

SCHEMA_VERSION = '1'

# ---------------------------------------------------------------- 常量 / 约定
ISO_FMT = '%Y-%m-%dT%H:%M:%S'
SENTINEL_BIRTHDAY = '1970-01-01T00:00:00'      # 「未设置生日」哨兵（沿用 account_state.seeded.json）

DEFAULT_SERVER_ID_BASE = 10_000_000_000        # D1：真账号 10015354380 同量级
DEFAULT_ENTITY_ID_BASE = 1_000_001             # 与已验证模板 characters[].ServerId 一致
DEFAULT_ENTITY_ID_STRIDE = 100_000             # 每账号预留 10 万个实体 id，跨账号不撞
DEFAULT_SESSION_TTL_SECONDS = 30 * 24 * 3600   # D4
DEFAULT_CALL_NAME = u'老师'                     # 国服对玩家的默认称呼（模板/抓包一致）
DEFAULT_NICKNAME_PREFIX = u'老师'

# AccountDB 22 字段的**顺序**（= dto_schema_full_v2.json 里 AccountDB.fields 的顺序）
ACCOUNT_DB_FIELDS = [
    'ServerId', 'Nickname', 'CallName', 'DevId', '<REDACTED_DEVID>', 'Level', 'Exp', 'Comment',
    'LobbyMode', 'RepresentCharacterServerId', 'MemoryLobbyUniqueId', 'LastConnectTime',
    'BirthDay', 'CallNameUpdateTime', 'PublisherAccountId', 'RetentionDays', 'VIPLevel',
    'CreateDate', 'UnReadMailCount', 'LinkRewardDate', 'LastReturningDate', 'Location',
]

# 实体 id（CharacterDB.ServerId / CafeDBId）的号段数：account 序号 → 号段 = 序号 % BANDS。
# 为什么取模：实体 id 必须**小**（官方是 1000001 量级，7 位）。直接用 server_id 序号做乘数，
# 迁移那个 10015354380 的号会算出 1.5e13 的实体 id —— 13 位数，任何客户端 int32 截断都会踩到
# 「官方永不出现」的分支。取模后最大 id = 1000001 + (BANDS-1)*STRIDE ≈ 1.0e8 < 2^31。
# 代价：跨账号唯一性以 BANDS 个账号为周期；**账号内唯一性始终成立**（这才是协议真正要求的）。
ENTITY_ID_BANDS = 1000
INT32_MAX = 2 ** 31 - 1

# 状态块 → blob kind。40 个状态块聚成 21 个 kind，粒度 = 「谁在写」= 协议族边界。
# 一律 payload = {状态块名: 值}，这样 build_state_for() 只需要 dict.update()，无 per-kind 分支。
BLOB_LAYOUT = {
    'option':      ['option', 'restrictions', 'functionClose'],
    'auth':        ['auth'],
    'characters':  ['characters', 'tssCharacters', 'weapons', 'costumes'],
    'equipment':   ['equipments', 'gears'],
    'items':       ['items', 'expiryItems'],
    'echelons':    ['echelons', 'arenaEchelon'],
    'memory_lobby': ['memoryLobby'],
    'emblems':     ['emblems'],
    'currency':    ['currencies', 'expiredCurrency', 'accountCurrency'],
    'cafe':        ['cafe'],
    'arena':       ['arena'],
    'raid':        ['raid', 'eliminateRaid'],
    'clan':        ['clan'],
    'momo_talk':   ['momotalks'],
    'scenario':    ['scenarios'],
    'campaign':    ['campaign'],
    'craft':       ['craft'],
    'billing':     ['billing'],
    'event':       ['eventContent', 'shop', 'contentSweep', 'multiFloorRaid', 'timeAttack'],
    'social':      ['attachment', 'stickerBook', 'settings'],
    'progress':    ['missionProgress', 'eventMissionProgress', 'battlePassMissionProgress'],
}
BLOB_KINDS = list(BLOB_LAYOUT)
KIND_OF_KEY = {}
for _kind, _keys in BLOB_LAYOUT.items():
    for _k in _keys:
        KIND_OF_KEY[_k] = _kind
# 由 accounts 行的列重建、不进 blob 的那个块
ROW_BACKED_KEYS = ('account',)
STATE_KEYS = list(ROW_BACKED_KEYS) + [k for keys in BLOB_LAYOUT.values() for k in keys]

META = '_meta'
MX_TOKEN_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


# ---------------------------------------------------------------- 异常

# [PATCH-PY-20261118-realauthdb] 真值分级获取（缓存→管理接口→影子→默认）
_REAL_CACHE = {}          # server_id -> (ts, dict)
_REAL_TTL = 60.0
_ADMIN_URL = os.environ.get("SHITTIM_ADMIN_URL", "http://127.0.0.1:5000").rstrip("/")
_SRV_CONFIG_JSON = os.environ.get("SHITTIM_CONFIG_JSON", "/www/wwwroot/ba_srv/Config/Config.json")
_ADMIN_KEY_ENV = os.environ.get("SHITTIM_ADMIN_API_KEY", "") or ""
_ADMIN_KEY = _ADMIN_KEY_ENV
_ADMIN_KEY_RESOLVED = bool(_ADMIN_KEY_ENV)
_ADMIN_KEY_WARNED = [False]


def _find_admin_key(obj, depth=0):
    if depth > 4 or not isinstance(obj, dict):
        return ""
    for k, v in obj.items():
        if k == "AdminApiKey" and isinstance(v, str) and v.strip():
            return v.strip()
    for v in obj.values():
        if isinstance(v, dict):
            got = _find_admin_key(v, depth + 1)
            if got:
                return got
    return ""


def _resolve_admin_key():
    global _ADMIN_KEY, _ADMIN_KEY_RESOLVED
    if _ADMIN_KEY_RESOLVED:
        return _ADMIN_KEY
    try:
        _j = __import__("json")
        with open(_SRV_CONFIG_JSON, encoding="utf-8") as f:
            got = _find_admin_key(_j.load(f))
        if got:
            _ADMIN_KEY = got
            _ADMIN_KEY_RESOLVED = True
            return got
    except Exception:
        pass
    _ADMIN_KEY = ""
    _ADMIN_KEY_RESOLVED = True
    if not _ADMIN_KEY_WARNED[0]:
        _ADMIN_KEY_WARNED[0] = True
        try:
            sys.stderr.write("[realdb][FATAL] no admin key configured; real account values DISABLED\n")
            sys.stderr.flush()
        except Exception:
            pass
    return ""
_real_warn = None          # 测试可注入


def _warn(msg):
    try:
        if _real_warn:
            _real_warn(msg)
        else:
            sys.stderr.write("[WARN][realdb] %s\n" % msg)
    except Exception:
        pass


def _http_json(path, timeout):
    _key = _resolve_admin_key()
    if not _key:
        raise RuntimeError("no admin key")
    req = urllib.request.Request(_ADMIN_URL + path, headers={"X-Admin-Key": _key, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if getattr(r, "status", 200) != 200:
            raise RuntimeError("http %s" % getattr(r, "status", "?"))
        body = r.read()
    if not body:
        raise ValueError("empty body")
    return json.loads(body.decode("utf-8"))


def _to_int(v, dflt):
    try:
        if isinstance(v, bool) or v is None:
            return dflt
        n = int(v)
        return n if n >= 0 else dflt
    except Exception:
        return dflt


def _to_str(v, dflt):
    if not isinstance(v, str):
        return dflt
    s = v.strip()
    return s if s else dflt


def _to_time(v, dflt):
    if not isinstance(v, str):
        return dflt
    s = v.strip()
    if not s or s.startswith("0001-01-01"):
        return dflt
    return s


def _pick_ci(raw, names):
    """大小写不敏感 + 多别名取值；返回 (found, value)。"""
    if not isinstance(raw, dict):
        return False, None
    low = {}
    for k, v in raw.items():
        if isinstance(k, str):
            low.setdefault(k.lower(), v)
    for n in names:
        if n in raw:
            return True, raw[n]
        if isinstance(n, str) and n.lower() in low:
            return True, low[n.lower()]
    return False, None


_FIELD_SPEC = (
    ("Level", ("level", "Level", "LEVEL", "lv"), _to_int, None),
    ("Exp", ("exp", "Exp", "EXP", "experience"), _to_int, None),
    ("VIPLevel", ("vipLevel", "VIPLevel", "VipLevel"), _to_int, None),
    ("UnReadMailCount", ("unReadMailCount", "UnReadMailCount", "unreadMailCount"), _to_int, None),
    ("Nickname", ("nickname", "Nickname", "nickName", "NickName"), _to_str, None),
    ("CallName", ("callName", "CallName", "callname"), _to_str, None),
    ("Comment", ("comment", "Comment"), _to_str, None),
    ("State", ("state", "State"), _to_int, None),
    ("RepresentCharacterServerId", ("representCharacterServerId", "RepresentCharacterServerId", "representCharacterUniqueId"), _to_int, None),
    ("PublisherAccountId", ("publisherAccountId", "PublisherAccountId", "publisherId"), _to_int, None),
    ("LastConnectTime", ("lastConnectTime", "LastConnectTime", "lastLoginAt"), _to_time, None),
    ("CreateDate", ("createDate", "CreateDate", "createdAt"), _to_time, None),
)


def fetch_real_account_fields(server_id, timeout=1.5, allow_cache=True):
    """-> dict(部分字段)。任何失败都返回 {} 并 WARN，绝不抛。"""
    sid = str(server_id)
    if not sid or sid in ("0", "None"):
        return {}
    now = time.time()
    if allow_cache:
        hit = _REAL_CACHE.get(sid)
        if hit and now - hit[0] <= _REAL_TTL:
            return dict(hit[1])
    try:
        raw = _http_json("/api/admin/account/%s/detail" % sid, timeout)
        if isinstance(raw, dict) and isinstance(raw.get("Data"), dict):
            raw = raw["Data"]
        if not isinstance(raw, dict):
            raise ValueError("not a json object")
    except Exception as e:
        _warn("serverId=%s admin-api failed: %r" % (sid, e))
        return {}
    out = {}
    for _row in _FIELD_SPEC:
        _dst, _names, _conv, _dflt = _row
        try:
            _found, _val = _pick_ci(raw, _names)
            if _found:
                out[_dst] = _conv(_val, _dflt)
        except Exception as e:
            _warn("serverId=%s field=%s coerce failed: %r" % (sid, _dst, e))
    if not out:
        _warn("serverId=%s admin-api returned no usable fields" % sid)
        return {}
    _REAL_CACHE[sid] = (now, dict(out))
    return out


def invalidate_real_cache(server_id=None):
    if server_id is None:
        _REAL_CACHE.clear()
    else:
        _REAL_CACHE.pop(str(server_id), None)


def merge_real_account_db(db, server_id, timeout=1.5):
    """逐字段覆盖；单字段失败不影响其它字段。"""
    try:
        real = fetch_real_account_fields(server_id, timeout=timeout)
    except Exception as e:
        _warn("serverId=%s fetch crashed: %r" % (server_id, e))
        return db
    for k, v in real.items():
        if v is None:
            continue
        try:
            db[k] = v
        except Exception:
            pass
    return db


# [PATCH-PY-20261118-wire] shittim_server_id：迁移/记录/反查（内联，单文件部署）
_SID_CACHE = {}
_SID_LIST_TTL = 60.0


def sid_ensure_column(conn):
    cur = conn.cursor(); cur.execute("PRAGMA table_info(accounts)")
    if "shittim_server_id" in [r[1] for r in cur.fetchall()]:
        return False
    cur.execute("ALTER TABLE accounts ADD COLUMN shittim_server_id INTEGER DEFAULT 0")
    conn.commit(); return True


def sid_record(stored, observed):
    try: o = int(observed or 0)
    except Exception: o = 0
    if o <= 0: return int(stored or 0)
    return o


def sid_list_accounts(timeout=1.5):
    now = time.time(); hit = _SID_CACHE.get("acct")
    if hit and now - hit[0] <= _SID_LIST_TTL: return hit[1]
    raw = _http_json("/api/admin/accounts", timeout)
    if isinstance(raw, dict): raw = raw.get("Data") or raw.get("data") or raw.get("accounts") or []
    if not isinstance(raw, list): raise ValueError("accounts list not a list")
    _SID_CACHE["acct"] = (now, raw); return raw


def sid_lookup(accounts, pub_id):
    try: want = int(pub_id or 0)
    except Exception: return 0
    if want <= 0: return 0
    for a in accounts or []:
        if not isinstance(a, dict): continue
        for k in ("publisherAccountId", "PublisherAccountId", "pubId", "pub_id"):
            if k in a:
                try:
                    if int(a.get(k) or 0) == want:
                        for sk in ("serverId", "ServerId", "accountServerId"):
                            if sk in a: return int(a.get(sk) or 0)
                except Exception: pass
    return 0


def sid_resolve(pub_id, stored, timeout=1.5):
    try: sid = int(stored or 0)
    except Exception: sid = 0
    if sid > 0: return sid, "stored"
    try:
        sid = sid_lookup(sid_list_accounts(timeout), pub_id)
        return (sid, "list") if sid > 0 else (0, "not-found")
    except Exception:
        return 0, "list-failed"


def resolve_sid_for_account(account):
    try: pub = int(getattr(account, "publisher_account_id", 0) or 0)
    except Exception: pub = 0
    try: stored = int(getattr(account, "shittim_server_id", 0) or 0)
    except Exception: stored = 0
    try: sid, src = sid_resolve(pub, stored)
    except Exception as e:
        _warn("sid resolve crashed: %r" % (e,)); return 0
    if sid <= 0:
        _warn("stored=%s pub=%s no shittim id (%s) -> shadow" % (stored, pub, src)); return 0
    try:
        if sid != stored: account.shittim_server_id = sid
    except Exception: pass
    return sid

# [PATCH-PY-20261118-fallbackid] identify 兜底身份（单账号部署形态专用）
_FALLBACK_WARNED = [False]
# [PATCH-PY-20261118-P5] 兜底号 314816420 -> 9000000001（卡号值域之外，永不撞真实卡）
DEFAULT_FALLBACK_PUBLISHER_ID = 9000000001


def _log_info(msg):
    try:
        sys.stderr.write("[INFO][fallback] " + str(msg) + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def _warn_once(msg):
    if _FALLBACK_WARNED[0]:
        return
    _FALLBACK_WARNED[0] = True
    try:
        sys.stderr.write("[WARN][fallback] " + str(msg) + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def _find_key_named(obj, want, depth=0):
    if depth > 4 or not isinstance(obj, dict):
        return None
    for k, v in obj.items():
        if k == want and not isinstance(v, (dict, list)):
            return v
    for v in obj.values():
        if isinstance(v, dict):
            got = _find_key_named(v, want, depth + 1)
            if got is not None:
                return got
    return None


def _fallback_publisher_id():
    v = (os.environ.get("BA_FALLBACK_PUBLISHER_ID") or "").strip()
    if v.isdigit() and int(v) > 0:
        _log_info("publisher_id=" + v + " from env BA_FALLBACK_PUBLISHER_ID")
        return int(v)
    try:
        _j = __import__("json")
        with open(_SRV_CONFIG_JSON, encoding="utf-8") as f:
            cfg = _j.load(f)
        for k in ("FallbackPublisherId", "FallbackPublisherID", "fallbackPublisherId"):
            got = _find_key_named(cfg, k)
            if got is not None and str(got).isdigit() and int(got) > 0:
                _log_info("publisher_id=" + str(got) + " from Config.json/" + k)
                return int(got)
    except Exception:
        pass
    _log_info("publisher_id=%d from hardcoded default" % DEFAULT_FALLBACK_PUBLISHER_ID)
    return DEFAULT_FALLBACK_PUBLISHER_ID


class AccountServiceError(Exception):
    u"""账号服务的基类异常。"""


class AuthRejected(AccountServiceError):
    u"""请求里没有可用的稳定身份、或违反 token 稳定策略 —— 拒绝签发会话。"""


class BlobConflict(AccountServiceError):
    u"""save_blob(expected_revision=...) 撞版本：有人已经改过这块状态。"""


class TemplateMissing(AccountServiceError):
    u"""新账号模板缺失（account_template.json）；先跑 --make-template。"""


class SchemaError(AccountServiceError):
    u"""库结构不对/版本不对。"""


# ---------------------------------------------------------------- 时间工具
def now_naive() -> datetime:
    u"""服务端本地时间，**naive**（无 tzinfo）。协议里的 DateTime 就是无时区语义。"""
    return datetime.now().replace(microsecond=0)


def to_iso(value: Any) -> Optional[str]:
    u"""任何时间表示 → 'YYYY-MM-DDTHH:MM:SS'（无时区）。None 进 None 出。

    这是本文件**唯一**允许产出时间字符串的地方：绝不 str(datetime.now())、绝不 isoformat()
    （isoformat 带 microsecond 或 '+00:00' 时区尾巴，客户端 DateTime 解析会挑食）。
    """
    if value is None or value == '':
        return None
    if isinstance(value, str):
        return normalize_iso(value)
    if isinstance(value, datetime):
        return value.replace(tzinfo=None, microsecond=0).strftime(ISO_FMT)
    if isinstance(value, (int, float)):
        return to_iso(datetime.fromtimestamp(value))
    if hasattr(value, 'strftime'):
        return value.strftime(ISO_FMT)
    raise TypeError(u'无法转成 ISO 时间: %r' % (value,))


_ISO_PARTS_RE = re.compile(
    r'^(\d{4})-(\d{1,2})-(\d{1,2})'
    r'(?:[T ](\d{1,2}):(\d{2})(?::(\d{2}))?)?')


def normalize_iso(text: str) -> str:
    u"""把客户端/别处给的时间串收敛成 'YYYY-MM-DDTHH:MM:SS'（丢掉毫秒与时区尾巴）。

    故意不用 isoformat()/fromisoformat() 当主路径：前者会带 '+00:00' 或毫秒，后者对
    '2026-11-14T12:00:00Z' 这类串在不同 Python 版本行为不同。协议要的只有一种形态。
    """
    s = str(text).strip().replace(' ', 'T')
    s = re.sub(r'(\.\d+)?(Z|[+-]\d{2}:?\d{2})$', '', s)
    m = _ISO_PARTS_RE.match(s)
    if m:
        y, mo, d, hh, mm, ss = m.groups()
        return datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0),
                        int(ss or 0)).strftime(ISO_FMT)
    raise ValueError(u'不是合法的无时区时间串: %r' % (text,))


def parse_iso(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    return datetime.strptime(normalize_iso(text), ISO_FMT)


# ---------------------------------------------------------------- 数据类
@dataclass
class Identity:
    u"""一次 auth 请求里能拿到的全部身份线索（= Account_Auth 请求体解出来的东西）。"""
    dev_id: str
    device_unique_id: Optional[str] = None
    token: Optional[str] = None
    publisher_account_id: int = 0
    dev_id_source: str = 'DevId'          # DevId / DeviceUniqueId
    protocol: Optional[int] = None         # 显式 Protocol，或从 Hash 高位解出
    counter: Optional[int] = None          # Hash 低位（客户端请求计数器）
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        uid = dict((k, v) for k, v in asdict(self).items() if k != 'raw')
        uid['token'] = _mask(self.token)
        return uid


@dataclass
class Account:
    u"""accounts 表的一行。字段名 ↔ 列名一一对应（见 schema_*.sql）。"""
    server_id: int
    dev_id: str
    device_unique_id: Optional[str] = None
    sdk_token: Optional[str] = None
    publisher_account_id: int = 0
    nickname: str = ''
    call_name: str = ''
    state: int = 1
    level: int = 1
    exp: int = 0
    comment: str = ''
    lobby_mode: int = 1
    represent_character_server_id: int = 0
    memory_lobby_unique_id: int = 0
    location: str = ''
    birthday: Optional[str] = None
    call_name_update_time: Optional[str] = None
    link_reward_date: Optional[str] = None
    last_returning_date: Optional[str] = None
    retention_days: Optional[int] = 1
    vip_level: Optional[int] = 0
    unread_mail_count: Optional[int] = 0
    next_entity_id: int = DEFAULT_ENTITY_ID_BASE
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None
    token_seen_at: Optional[str] = None
    login_count: int = 0

    @property
    def account_id(self) -> int:
        u"""对齐客户端语义：AccountId 是 SessionKey.AccountServerId 的影子。"""
        return self.server_id

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['sdk_token'] = _mask(self.sdk_token)
        return d


@dataclass(frozen=True)
class SessionKey:
    u"""会话凭据。结构严格对齐客户端的 MX.GameLogic.SessionKey（report/76 §1.1）。"""
    account_server_id: int
    mx_token: str

    @property
    def account_id(self) -> int:
        return self.account_server_id

    def to_dict(self) -> Dict[str, Any]:
        u"""直接塞进 Account_Auth 响应的 SessionKey 字段。"""
        return {'AccountServerId': self.account_server_id, 'MxToken': self.mx_token}

    def is_well_formed(self) -> bool:
        return bool(MX_TOKEN_RE.match(self.mx_token or ''))


def _mask(secret: Optional[str]) -> Optional[str]:
    u"""日志/JSON 里不打全量 token。"""
    if not secret:
        return secret
    s = str(secret)
    return s if len(s) <= 8 else '%s...%s(%d)' % (s[:4], s[-4:], len(s))


# ---------------------------------------------------------------- 配置
@dataclass
class Config:
    db_path: str = os.path.join(HERE, 'ba_accounts.sqlite3')
    dialect: str = 'sqlite'                       # sqlite / mysql
    mysql_host: str = '127.0.0.1'
    mysql_port: int = 3306
    mysql_user: str = 'root'
    mysql_password: str = ''
    mysql_database: str = 'ba_accounts'
    server_id_base: int = DEFAULT_SERVER_ID_BASE
    entity_id_base: int = DEFAULT_ENTITY_ID_BASE
    entity_id_stride: int = DEFAULT_ENTITY_ID_STRIDE
    session_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS
    max_active_sessions: int = 1                  # 0 = 不限
    touch_session_on_resolve: bool = True
    require_token_stable: bool = False            # True：SDK token 变了就拒登（默认关，见 §1.4）
    nickname_prefix: str = DEFAULT_NICKNAME_PREFIX
    template_path: str = TEMPLATE_PATH
    frozen_now: Optional[str] = None              # 自检/可复现：固定「现在」
    schema_file: Optional[str] = None             # 手工指定 DDL 文件

    @classmethod
    def from_env(cls, **overrides) -> 'Config':
        env = os.environ
        cfg = cls(
            db_path=env.get('BA_ACCOUNT_DB', cls.db_path),
            dialect=env.get('BA_ACCOUNT_DIALECT', 'sqlite').lower(),
            mysql_host=env.get('BA_MYSQL_HOST', '127.0.0.1'),
            mysql_port=int(env.get('BA_MYSQL_PORT', '3306')),
            mysql_user=env.get('BA_MYSQL_USER', 'root'),
            mysql_password=env.get('BA_MYSQL_PASSWORD', ''),
            mysql_database=env.get('BA_MYSQL_DATABASE', 'ba_accounts'),
            server_id_base=int(env.get('BA_SERVER_ID_BASE', DEFAULT_SERVER_ID_BASE)),
            entity_id_base=int(env.get('BA_ENTITY_ID_BASE', DEFAULT_ENTITY_ID_BASE)),
            entity_id_stride=int(env.get('BA_ENTITY_ID_STRIDE', DEFAULT_ENTITY_ID_STRIDE)),
            session_ttl_seconds=int(env.get('BA_SESSION_TTL', DEFAULT_SESSION_TTL_SECONDS)),
            max_active_sessions=int(env.get('BA_MAX_ACTIVE_SESSIONS', '1')),
            require_token_stable=env.get('BA_REQUIRE_TOKEN_STABLE', '0') in ('1', 'true', 'yes'),
            frozen_now=env.get('BA_FROZEN_NOW') or None,
        )
        for k, v in overrides.items():
            if v is not None:
                setattr(cfg, k, v)
        return cfg


# ---------------------------------------------------------------- 服务
class AccountService(object):
    u"""账号服务：一个实例管一个库。线程安全（连接 thread-local，写操作走显式事务）。"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.from_env()
        self.dialect = (self.config.dialect or 'sqlite').lower()
        if self.dialect not in ('sqlite', 'mysql'):
            raise AccountServiceError(u'未知方言: %s（只支持 sqlite / mysql）' % self.dialect)
        self._local = threading.local()
        self._template_cache = None
        self._pymysql = None
        if self.dialect == 'mysql':
            try:
                import pymysql  # noqa: F401
                import pymysql.cursors
                self._pymysql = pymysql
            except ImportError:
                raise AccountServiceError(
                    u'dialect=mysql 需要 pymysql（pip install pymysql）；'
                    u'没装就用 dialect=sqlite 或先在宝塔里建好表再说')

    # ------------------------------------------------ 连接 / 事务
    def _connect(self):
        if self.dialect == 'sqlite':
            conn = sqlite3.connect(self.config.db_path, timeout=10.0,
                                   isolation_level=None, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA foreign_keys = ON')
            conn.execute('PRAGMA busy_timeout = 5000')
            try:
                conn.execute('PRAGMA journal_mode = WAL')
            except sqlite3.DatabaseError:
                pass                            # 只读介质/内存库时会失败，不影响功能
            return conn
        conn = self._pymysql.connect(
            host=self.config.mysql_host, port=self.config.mysql_port,
            user=self.config.mysql_user, password=self.config.mysql_password,
            database=self.config.mysql_database, charset='utf8mb4',
            cursorclass=self._pymysql.cursors.DictCursor, autocommit=False)
        return conn

    def close(self):
        conn = getattr(self._local, 'conn', None)
        if conn is not None:
            try:
                conn.close()
            finally:
                self._local.conn = None

    def _conn(self):
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = self._connect()
            self._local.conn = conn
        return conn

    def _adapt(self, sql: str) -> str:
        u"""SQL 一律用 '?' 占位写，MySQL 方言换成 '%s'。"""
        return sql if self.dialect == 'sqlite' else sql.replace('?', '%s')

    def _execute(self, sql: str, args: Iterable = ()):
        cur = self._conn().cursor()
        cur.execute(self._adapt(sql), tuple(args))
        return cur

    def _exec_count(self, sql: str, args: Iterable = ()) -> int:
        u"""执行写语句并返回受影响行数（游标用完即关）。"""
        cur = self._execute(sql, args)
        n = cur.rowcount
        cur.close()
        return n

    def _fetchone(self, sql: str, args: Iterable = ()):
        cur = self._execute(sql, args)
        row = cur.fetchone()
        cur.close()
        return row

    def _fetchall(self, sql: str, args: Iterable = ()):
        cur = self._execute(sql, args)
        rows = cur.fetchall()
        cur.close()
        return rows

    @contextlib.contextmanager
    def transaction(self):
        u"""显式事务。SQLite 用 BEGIN IMMEDIATE 一开始就拿写锁（避免读后升级写死锁）。"""
        conn = self._conn()
        if self.dialect == 'sqlite':
            if conn.in_transaction:
                yield conn
                return
            conn.execute('BEGIN IMMEDIATE')
            try:
                yield conn
            except BaseException:
                conn.rollback()
                raise
            conn.commit()
            return
        conn.begin()
        try:
            yield conn
        except BaseException:
            conn.rollback()
            raise
        conn.commit()

    def _for_update(self) -> str:
        return '' if self.dialect == 'sqlite' else ' FOR UPDATE'

    # ------------------------------------------------ 建表
    def schema_file(self) -> str:
        if self.config.schema_file:
            return self.config.schema_file
        return SCHEMA_SQLITE_PATH if self.dialect == 'sqlite' else SCHEMA_MYSQL_PATH

    def init_schema(self, verbose: bool = False) -> int:
        u"""执行 DDL。幂等（全是 IF NOT EXISTS），返回执行的语句数。"""
        path = self.schema_file()
        if not os.path.exists(path):
            raise SchemaError(u'找不到 DDL 文件: %s' % path)
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        stmts = split_sql(text)
        conn = self._conn()
        for stmt in stmts:
            if verbose:
                print(u'  [ddl] %s' % stmt.splitlines()[0][:90])
            cur = conn.cursor()
            cur.execute(stmt)
            cur.close()
        if self.dialect != 'sqlite':
            conn.commit()
        self._check_schema_version()
        return len(stmts)

    def _check_schema_version(self):
        try:
            row = self._fetchone("SELECT v FROM schema_meta WHERE k = 'schema_version'")
        except Exception:                        # 老库没有 schema_meta 也要能跑
            return
        if row is None:
            return
        found = row['v'] if not isinstance(row, (list, tuple)) else row[0]
        if str(found) != SCHEMA_VERSION:
            raise SchemaError(u'库 schema_version=%s，本服务需要 %s（先迁移）'
                              % (found, SCHEMA_VERSION))

    # ------------------------------------------------ 时间
    def now(self) -> datetime:
        if self.config.frozen_now:
            return parse_iso(self.config.frozen_now)
        return now_naive()

    def now_iso(self) -> str:
        return to_iso(self.now())

    # ------------------------------------------------ ① identify
    def identify(self, req: Any) -> Identity:
        u"""从 Account_Auth(1002) 请求体提取身份。

        接受：dict（已解密的请求明文）/ JSON 字符串 / UTF-8 bytes。
        字段按 Account_Auth 实测形态取（协议体顶层扁平），但也容忍外面包一层请求 DTO。
        Hash = (协议号 << 32) | 计数器 → 高位=协议号，低位=计数器（本地已实测）。
        """
        body, protocol, counter = _decode_request(req)

        dev_id_raw = _pick(body, ('DevId', '<REDACTED_DEVID>', 'devId', '<REDACTED_DEVID>'))
        duid = _pick(body, ('DeviceUniqueId', '<REDACTED_DEVID>', 'DUID', 'deviceUniqueId'))
        token = _pick(body, ('Token', '<REDACTED_TOKEN>', 'sdkToken'))
        pub = _pick(body, ('PublisherAccountId', 'PublisherID', 'publisherAccountId'))

        dev_id = ''
        source = 'DevId'
        if dev_id_raw is not None and str(dev_id_raw).strip() not in ('', '0', 'null', 'None'):
            dev_id = str(dev_id_raw).strip()
        elif duid and str(duid).strip():
            dev_id = 'duid:%s' % str(duid).strip().lower()
            source = 'DeviceUniqueId'
        else:
            _fb = _fallback_publisher_id()
            if _fb <= 0:
                raise AuthRejected(
                    u'请求里既没有 DevId 也没有 DeviceUniqueId —— 没有稳定身份键就拒绝建号，'
                    u'否则每次 token 轮换都会变成一个新账号')
            _warn_once('identify: no DevId/DeviceUniqueId, falling back to publisher_id=%s' % _fb)
            return Identity(dev_id=str(_fb), device_unique_id=None, token=None,
                            publisher_account_id=_fb, dev_id_source='fallback',
                            protocol=protocol, counter=counter, raw=body)

        duid_c = (str(duid).strip().lower() or None) if duid else None
        token_c = (str(token).strip() or None) if token else None

        publisher_account_id = 0
        if pub not in (None, '', 0, '0'):
            try:
                publisher_account_id = int(pub)
            except (TypeError, ValueError):
                publisher_account_id = 0
        elif dev_id.isdigit():
            # 实测一次抓包中 PublisherAccountId == DevId（推断关系，非源码证据）
            publisher_account_id = int(dev_id)

        return Identity(dev_id=dev_id, device_unique_id=duid_c, token=token_c,
                        publisher_account_id=publisher_account_id,
                        dev_id_source=source, protocol=protocol, counter=counter,
                        raw=body)

    # ------------------------------------------------ ② get_or_create_account
    def get_or_create_account(self, identity: Identity, record_login: bool = True) -> Account:
        u"""按 dev_id 查账号；没有就新建（同事务里发 server_id + 写 21 个初始 blob）。

        record_login=True 时顺手记账（sdk_token / device_unique_id / last_login_at / login_count），
        也就是「登录即落库」。并发首登靠 UNIQUE(dev_id) 兜底：插入失败就回查。
        """
        row = self._fetchone('SELECT * FROM accounts WHERE dev_id = ?', (identity.dev_id,))
        if row is None:
            try:
                return self._create_account(identity)
            except Exception as exc:            # noqa: BLE001 —— 只吞唯一键冲突
                if not _is_unique_violation(exc):
                    raise
                row = self._fetchone('SELECT * FROM accounts WHERE dev_id = ?', (identity.dev_id,))
                if row is None:
                    raise
        account = row_to_account(row)
        if record_login:
            account = self._stamp_login(account, identity)
        return account

    def _create_account(self, identity: Identity, server_id: Optional[int] = None) -> Account:
        u"""新建账号。server_id=None 时发新号；给了值就按指定号建（迁移历史账号用）。"""
        with self.transaction() as conn:
            if server_id is None:
                server_id = self._alloc_server_id(conn)
            else:
                server_id = int(server_id)
                if server_id < self.config.server_id_base:
                    raise AccountServiceError(
                        u'指定 server_id=%s 小于基数 %s：DDL 的 CHECK 会拒绝；'
                        u'要用更小的号必须先改 server_id_base 并 DROP CHECK'
                        % (server_id, self.config.server_id_base))
                self._bump_allocator(conn, server_id + 1)
            ordinal = max(0, server_id - self.config.server_id_base)
            band = ordinal % ENTITY_ID_BANDS
            next_entity = self.config.entity_id_base + band * self.config.entity_id_stride
            if next_entity > INT32_MAX:
                raise AccountServiceError(
                    u'实体 id 越界（%s > int32）：entity_id_base/stride/ENTITY_ID_BANDS 配得太肥'
                    % next_entity)
            now = self.now_iso()
            nickname = (self.config.nickname_prefix or '') + '%04d' % (ordinal + 1)
            account = Account(
                server_id=server_id,
                dev_id=identity.dev_id,
                device_unique_id=identity.device_unique_id,
                sdk_token=identity.token,
                publisher_account_id=identity.publisher_account_id,
                nickname=nickname,
                call_name=DEFAULT_CALL_NAME,
                state=1,
                level=1,
                exp=0,
                comment='',
                lobby_mode=1,
                represent_character_server_id=next_entity,   # 首次登录的 1 号学生
                memory_lobby_unique_id=0,
                location='',
                birthday=None,
                call_name_update_time=now,
                link_reward_date=None,
                last_returning_date=None,
                retention_days=1,
                vip_level=0,
                unread_mail_count=0,
                next_entity_id=next_entity,
                created_at=now,
                last_login_at=now,
                token_seen_at=now if identity.token else None,
                login_count=1,
            )
            cols = list(asdict(account).keys())
            sql = 'INSERT INTO accounts (%s) VALUES (%s)' % (
                ', '.join(cols), ', '.join(['?'] * len(cols)))
            conn.cursor().execute(self._adapt(sql), tuple(getattr(account, c) for c in cols))

            state = self.bootstrap_state(account)
            self._write_blobs(conn, server_id, state)
            # 初始学生/咖啡馆已经吃掉了实体 id，把游标落库（否则第一次 alloc 会撞号）
            conn.cursor().execute(
                self._adapt('UPDATE accounts SET next_entity_id = ? WHERE server_id = ?'),
                (account.next_entity_id, server_id))
            return account

    def _alloc_server_id(self, conn) -> int:
        u"""从 id_alloc 发号：先读再 CAS 自增，冲突就重读重试（两方言同一套逻辑）。"""
        for _ in range(50):
            cur = conn.cursor()
            cur.execute(self._adapt('SELECT next_id FROM id_alloc WHERE name = ?' + self._for_update()),
                        ('server_id',))
            r = cur.fetchone()
            cur.close()
            if r is None:
                raise SchemaError(u'id_alloc 里没有 server_id 行（DDL 没跑全？）')
            nxt = int(r['next_id'] if not isinstance(r, (list, tuple)) else r[0])
            if nxt < self.config.server_id_base:
                nxt = self.config.server_id_base
            ucur = conn.cursor()
            ucur.execute(self._adapt(
                'UPDATE id_alloc SET next_id = next_id + 1 WHERE name = ? AND next_id = ?'),
                ('server_id', nxt))
            hit = ucur.rowcount
            ucur.close()
            if hit == 1:
                return nxt
        raise AccountServiceError(u'发号重试 50 次仍冲突，id_alloc 可能被外部改写')

    def _bump_allocator(self, conn, at_least: int) -> None:
        u"""把发号器推到至少 at_least（指定 server_id 建号后不能再用到这个号）。"""
        cur = conn.cursor()
        cur.execute(self._adapt('SELECT next_id FROM id_alloc WHERE name = ?' + self._for_update()),
                    ('server_id',))
        r = cur.fetchone()
        cur.close()
        if r is None:
            raise SchemaError(u'id_alloc 里没有 server_id 行（DDL 没跑全？）')
        cur_id = int(r['next_id'] if not isinstance(r, (list, tuple)) else r[0])
        if cur_id < at_least:
            conn.cursor().execute(self._adapt('UPDATE id_alloc SET next_id = ? WHERE name = ?'),
                                  (at_least, 'server_id'))

    def _stamp_login(self, account: Account, identity: Identity) -> Account:
        now = self.now_iso()
        sets, args = [], []
        if identity.token:
            if account.sdk_token and identity.token != account.sdk_token:
                if self.config.require_token_stable:
                    raise AuthRejected(
                        u'账号 %s 的 SDK token 变了（%s -> %s），require_token_stable=1 拒绝登录'
                        % (account.server_id, _mask(account.sdk_token), _mask(identity.token)))
            if identity.token != account.sdk_token:
                sets.append('sdk_token = ?')
                args.append(identity.token)
                account.sdk_token = identity.token
            sets.append('token_seen_at = ?')
            args.append(now)
            account.token_seen_at = now
        if identity.device_unique_id and identity.device_unique_id != account.device_unique_id:
            sets.append('device_unique_id = ?')
            args.append(identity.device_unique_id)
            account.device_unique_id = identity.device_unique_id
        if identity.publisher_account_id and identity.publisher_account_id != account.publisher_account_id:
            sets.append('publisher_account_id = ?')
            args.append(identity.publisher_account_id)
            account.publisher_account_id = identity.publisher_account_id
        sets.extend(['last_login_at = ?', 'login_count = login_count + 1'])
        args.extend([now, account.server_id])
        self._execute('UPDATE accounts SET %s WHERE server_id = ?' % ', '.join(sets), args)
        account.last_login_at = now
        account.login_count = (account.login_count or 0) + 1
        return account

    def record_login(self, account: Account, identity: Identity) -> Account:
        u"""显式记账（get_or_create_account(record_login=False) 后需要时用）。"""
        return self._stamp_login(account, identity)

    def create_account_at(self, identity: Identity, server_id: int) -> Account:
        u"""按**指定** server_id 建号（迁移历史账号用：保住客户端的存档文件名前缀）。

        已存在同号或同 dev_id 的账号就报错，不做静默覆盖。
        """
        server_id = int(server_id)
        if self.get_account(server_id) is not None:
            raise AccountServiceError(u'server_id 已存在: %s' % server_id)
        if self.get_account_by_dev_id(identity.dev_id) is not None:
            raise AccountServiceError(u'dev_id 已有账号: %s（要迁移请先删旧号）' % identity.dev_id)
        return self._create_account(identity, server_id=server_id)

    # ------------------------------------------------ ③ issue_session_key
    def issue_session_key(self, account: Account, client_ip: Optional[str] = None,
                          note: Optional[str] = None,
                          ttl_seconds: Optional[int] = None) -> SessionKey:
        u"""签发会话：uuid4 → 36 字符小写 GUID，对齐客户端 SessionKey.MxToken 形态。"""
        token = str(uuid.uuid4()).lower()
        ttl = self.config.session_ttl_seconds if ttl_seconds is None else int(ttl_seconds)
        now = self.now()
        issued = to_iso(now)
        expires = to_iso(now + timedelta(seconds=ttl))
        with self.transaction() as conn:
            keep = max(0, self.config.max_active_sessions - 1) if self.config.max_active_sessions > 0 else None
            if keep is not None:
                cur = conn.cursor()
                cur.execute(self._adapt(
                    'SELECT mx_token FROM sessions WHERE server_id = ? AND revoked = 0 '
                    'ORDER BY issued_at DESC'), (account.server_id,))
                rows = cur.fetchall()
                cur.close()
                for r in rows[keep:]:
                    tok = r['mx_token'] if not isinstance(r, (list, tuple)) else r[0]
                    conn.cursor().execute(
                        self._adapt('UPDATE sessions SET revoked = 1 WHERE mx_token = ?'), (tok,))
            conn.cursor().execute(self._adapt(
                'INSERT INTO sessions (mx_token, server_id, issued_at, expires_at, last_seen, '
                'revoked, client_ip, note) VALUES (?,?,?,?,?,?,?,?)'),
                (token, account.server_id, issued, expires, None, 0, client_ip,
                 note or u'issuer=account_service'))
        return SessionKey(account_server_id=account.server_id, mx_token=token)

    # ------------------------------------------------ ④ resolve_session
    def resolve_session(self, mx_token: Any, touch: Optional[bool] = None) -> Optional[Account]:
        u"""校验会话并取回账号。大小写不敏感（Shittim 用 OrdinalIgnoreCase 比字符串）。"""
        if not isinstance(mx_token, str):
            return None
        token = mx_token.strip().lower()
        if not token:
            return None
        row = self._fetchone(
            'SELECT a.*, s.expires_at AS _sess_expires, s.revoked AS _sess_revoked, '
            's.last_seen AS _sess_last_seen FROM sessions s '
            'JOIN accounts a ON a.server_id = s.server_id WHERE s.mx_token = ?', (token,))
        if row is None:
            return None
        d = dict(row)
        if int(d.get('_sess_revoked') or 0) != 0:
            return None
        exp = parse_iso(d.get('_sess_expires'))
        if exp is not None and exp <= self.now():
            return None
        account = row_to_account(d)
        do_touch = self.config.touch_session_on_resolve if touch is None else touch
        if do_touch:
            self._execute('UPDATE sessions SET last_seen = ? WHERE mx_token = ?',
                          (self.now_iso(), token))
        return account

    def revoke_session(self, mx_token: Any) -> bool:
        u"""撤销一个会话（Account_InvalidateToken(1016) 走这里）。返回是否真的撤了。"""
        if not isinstance(mx_token, str) or not mx_token.strip():
            return False
        return self._exec_count('UPDATE sessions SET revoked = 1 WHERE mx_token = ? AND revoked = 0',
                                (mx_token.strip().lower(),)) > 0

    def revoke_all_sessions(self, server_id: int) -> int:
        return self._exec_count('UPDATE sessions SET revoked = 1 WHERE server_id = ? AND revoked = 0',
                                (server_id,))

    def list_sessions(self, server_id: int) -> List[Dict[str, Any]]:
        rows = self._fetchall(
            'SELECT mx_token, issued_at, expires_at, last_seen, revoked, client_ip, note '
            'FROM sessions WHERE server_id = ? ORDER BY issued_at DESC', (server_id,))
        return [_rowdict(r) for r in rows]

    # ------------------------------------------------ ⑤⑥ blobs
    def load_blob(self, server_id: int, kind: str) -> Optional[Dict[str, Any]]:
        self._check_kind(kind)
        row = self._fetchone('SELECT payload FROM account_blobs WHERE server_id = ? AND kind = ?',
                             (server_id, kind))
        if row is None:
            return None
        payload = row['payload'] if not isinstance(row, (list, tuple)) else row[0]
        return json.loads(payload) if payload else {}

    def load_blob_with_meta(self, server_id: int, kind: str) -> Optional[Dict[str, Any]]:
        self._check_kind(kind)
        row = self._fetchone(
            'SELECT payload, revision, updated_at, updated_by FROM account_blobs '
            'WHERE server_id = ? AND kind = ?', (server_id, kind))
        if row is None:
            return None
        d = _rowdict(row)
        d['payload'] = json.loads(d['payload']) if d['payload'] else {}
        return d

    def save_blob(self, server_id: int, kind: str, payload: Dict[str, Any],
                  expected_revision: Optional[int] = None,
                  updated_by: Optional[str] = None) -> int:
        u"""写一个状态块，返回新的 revision。带 expected_revision 时做乐观锁。"""
        self._check_kind(kind)
        if not isinstance(payload, dict):
            raise TypeError(u'blob payload 必须是 dict（统一形态: {状态块名: 值}）')
        unknown = [k for k in payload if k not in BLOB_LAYOUT[kind]]
        if unknown:
            raise ValueError(u'kind=%s 不认识这些状态块: %s（允许: %s）'
                             % (kind, unknown, BLOB_LAYOUT[kind]))
        text = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        now = self.now_iso()
        if expected_revision is not None:
            hit = self._exec_count(
                'UPDATE account_blobs SET payload = ?, revision = revision + 1, updated_at = ?, '
                'updated_by = ? WHERE server_id = ? AND kind = ? AND revision = ?',
                (text, now, updated_by or u'account_service', server_id, kind, int(expected_revision)))
            if hit == 0:
                raise BlobConflict(u'blob %s/%s revision=%s 已被别人改过'
                                   % (server_id, kind, expected_revision))
            return int(expected_revision) + 1
        self._upsert_blob(self._conn(), server_id, kind, payload, updated_by or u'account_service',
                          now=now)
        row = self._fetchone('SELECT revision FROM account_blobs WHERE server_id = ? AND kind = ?',
                             (server_id, kind))
        return int(row['revision'] if not isinstance(row, (list, tuple)) else row[0])

    def delete_blob(self, server_id: int, kind: str) -> bool:
        self._check_kind(kind)
        return self._exec_count('DELETE FROM account_blobs WHERE server_id = ? AND kind = ?',
                                (server_id, kind)) > 0

    def all_blobs(self, server_id: int) -> Dict[str, Dict[str, Any]]:
        rows = self._fetchall('SELECT kind, payload FROM account_blobs WHERE server_id = ?',
                              (server_id,))
        out = {}
        for r in rows:
            d = _rowdict(r)
            out[d['kind']] = json.loads(d['payload']) if d['payload'] else {}
        return out

    @staticmethod
    def blob_kinds() -> List[str]:
        return list(BLOB_KINDS)

    @staticmethod
    def _check_kind(kind: str):
        if kind not in BLOB_LAYOUT:
            raise ValueError(u'未知 blob kind: %r（合法值: %s）' % (kind, ', '.join(BLOB_KINDS)))

    def _upsert_blob(self, conn, server_id: int, kind: str, payload: Dict[str, Any],
                     updated_by: str, now: Optional[str] = None) -> None:
        text = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        now = now or self.now_iso()
        if self.dialect == 'sqlite':
            sql = ('INSERT INTO account_blobs (server_id, kind, payload, revision, updated_at, updated_by) '
                   'VALUES (?,?,?,1,?,?) ON CONFLICT (server_id, kind) DO UPDATE SET '
                   'payload = excluded.payload, revision = account_blobs.revision + 1, '
                   'updated_at = excluded.updated_at, updated_by = excluded.updated_by')
            args = (server_id, kind, text, now, updated_by)
        else:
            sql = ('INSERT INTO account_blobs (server_id, kind, payload, revision, updated_at, updated_by) '
                   'VALUES (%s,%s,%s,1,%s,%s) ON DUPLICATE KEY UPDATE '
                   'payload = VALUES(payload), revision = revision + 1, '
                   'updated_at = VALUES(updated_at), updated_by = VALUES(updated_by)')
            args = (server_id, kind, text, now, updated_by)
        conn.cursor().execute(sql, args)

    def _write_blobs(self, conn, server_id: int, state: Dict[str, Any],
                     updated_by: str = u'bootstrap') -> None:
        for kind, keys in BLOB_LAYOUT.items():
            payload = dict((k, state[k]) for k in keys if k in state)
            self._upsert_blob(conn, server_id, kind, payload, updated_by)

    # ------------------------------------------------ ⑦ build_account_db_for
    def build_account_db_for(self, account: Account) -> Dict[str, Any]:
        base = self._build_account_db_for_shadow(account)
        try:
            sid = resolve_sid_for_account(account)
            base = merge_real_account_db(base, sid)
        except Exception as e:
            _warn("merge real fields failed sid=%r: %r" % (getattr(account, "server_id", 0), e))
        return base

    def _build_account_db_for_shadow(self, account: Account) -> Dict[str, Any]:
        u"""生成 AccountDB 的 22 个字段（键顺序 = schema 顺序；时间=无时区 ISO）。

        LastConnectTime ← last_login_at（没登录过则 created_at）
        CreateDate      ← created_at
        BirthDay        ← birthday，空则哨兵 1970-01-01T00:00:00（客户端还没走过 Account_BirthDay）
        CallNameUpdateTime ← call_name_update_time，空则 created_at
        """
        created = to_iso(account.created_at) or self.now_iso()
        return {
            'ServerId': int(account.server_id),
            'Nickname': account.nickname or '',
            'CallName': account.call_name or '',
            'DevId': account.dev_id or '',
            'State': int(account.state if account.state is not None else 1),
            'Level': int(account.level or 1),
            'Exp': int(account.exp or 0),
            'Comment': account.comment or '',
            'LobbyMode': int(account.lobby_mode if account.lobby_mode is not None else 1),
            'RepresentCharacterServerId': int(account.represent_character_server_id or 0),
            'MemoryLobbyUniqueId': int(account.memory_lobby_unique_id or 0),
            'LastConnectTime': to_iso(account.last_login_at) or created,
            'BirthDay': to_iso(account.birthday) or SENTINEL_BIRTHDAY,
            'CallNameUpdateTime': (to_iso(account.call_name_update_time) or ('0001-01-01T00:00:00' if not (getattr(account, 'nickname', '') or '').strip() else created)),
            'PublisherAccountId': int(account.publisher_account_id or 0),
            'RetentionDays': None if account.retention_days is None else int(account.retention_days),
            'VIPLevel': None if account.vip_level is None else int(account.vip_level),
            'CreateDate': created,
            'UnReadMailCount': None if account.unread_mail_count is None else int(account.unread_mail_count),
            'LinkRewardDate': to_iso(account.link_reward_date),
            'LastReturningDate': to_iso(account.last_returning_date),
            'Location': account.location or '',
        }

    # ------------------------------------------------ 状态拼装（对接响应构造层）
    def _template(self) -> Dict[str, Any]:
        if self._template_cache is None:
            path = self.config.template_path
            if not os.path.exists(path):
                raise TemplateMissing(
                    u'缺少新账号模板 %s —— 先跑：python account_service.py --make-template '
                    u'（源：proto/account_state.seeded.json）' % path)
            with open(path, 'r', encoding='utf-8') as f:
                self._template_cache = json.load(f)
            self.check_template(self._template_cache)
        return self._template_cache

    @staticmethod
    def check_template(state: Dict[str, Any]) -> None:
        u"""模板必须覆盖 41 个状态键（1 个走 accounts 行 + 40 个走 blob）。"""
        want = set(STATE_KEYS)
        got = set(k for k in state if not k.startswith('_'))
        missing, extra = want - got, got - want
        if missing or extra:
            raise TemplateMissing(u'模板状态键不匹配：缺 %s，多 %s' % (sorted(missing), sorted(extra)))

    def build_state_for(self, account: Account, strict: bool = False,
                        frozen_time: Optional[str] = None,
                        include_meta: bool = True, refresh: bool = True) -> Dict[str, Any]:
        u"""把 accounts 行 + 21 个 blob 拼回 build_response.py 认识的 41 键状态。

        直接喂给：build_response.Builder(schema, pmap, state)。_meta.frozenTime 决定
        ServerTimeTicks —— 线上必须是「现在」，否则客户端时钟/倒计时会被冻住。

        refresh=True（默认）时先按 server_id 重读 account 行：避免调用方拿着旧对象
        （比如 import_state/update_account 之后）拼出一份过期的 AccountDB。
        """
        if refresh:
            fresh = self.get_account(account.server_id)
            if fresh is not None:
                account = fresh
        tmpl = self._template()
        state: Dict[str, Any] = {}
        if include_meta:
            meta = copy.deepcopy(tmpl.get(META) or {})
            meta['frozenTime'] = frozen_time or self.now_iso()
            meta['serverId'] = account.server_id
            state[META] = meta
        state['account'] = merge_real_account_db(self.build_account_db_for(account), resolve_sid_for_account(account))
        blobs = self.all_blobs(account.server_id)
        for kind, keys in BLOB_LAYOUT.items():
            payload = blobs.get(kind)
            if payload is None:
                if strict:
                    raise AccountServiceError(u'账号 %s 缺 blob %s' % (account.server_id, kind))
                payload = dict((k, copy.deepcopy(tmpl.get(k))) for k in keys if k in tmpl)
            for k in keys:
                if k in payload:
                    state[k] = payload[k]
                elif k in tmpl:
                    state[k] = copy.deepcopy(tmpl[k])
        return state

    def bootstrap_state(self, account: Account) -> Dict[str, Any]:
        u"""新账号初始状态：模板深拷贝 + 身份字段重写。

        初始语义（沿用已验证的 account_state.seeded.json）：
          Level=1 / Exp=0 / State=1 / Comment="" / 3 个 1 级学生 / 28 种货币（信用点 100 万、AP 240、
          各类挑战券 3、其余 0）/ 无道具、无编队、无通关记录 / 一间 1 级咖啡馆。
        """
        state = copy.deepcopy(self._template())
        state.pop(META, None)
        self._rewrite_identity(state, account, renumber_entities=True)
        return state

    def import_state(self, account: Account, state: Dict[str, Any],
                     renumber_entities: bool = False,
                     updated_by: str = u'import') -> Dict[str, Any]:
        u"""把一份**现成的** account_state 灌进某个账号（= 迁移现有硬编码状态的正路）。

        与 bootstrap 的区别：不重排 students[].ServerId（否则编队/装备的引用全断），
        只做「必须与账号主键一致」的身份修正，并把实体发号游标推到已用最大值之后。
        """
        state = copy.deepcopy(state)
        state.pop(META, None)
        self.check_template(state)
        # 1) 账号行按状态里的 account 块覆盖（只取白名单字段，绝不改 server_id/dev_id）
        old = (state.get('account') or {})
        updatable = {
            'nickname': old.get('Nickname'), 'call_name': old.get('CallName'),
            'state': old.get('State'), 'level': old.get('Level'), 'exp': old.get('Exp'),
            'comment': old.get('Comment'), 'lobby_mode': old.get('LobbyMode'),
            'represent_character_server_id': old.get('RepresentCharacterServerId'),
            'memory_lobby_unique_id': old.get('MemoryLobbyUniqueId'),
            'birthday': old.get('BirthDay'), 'call_name_update_time': old.get('CallNameUpdateTime'),
            'publisher_account_id': old.get('PublisherAccountId'),
            'retention_days': old.get('RetentionDays'), 'vip_level': old.get('VIPLevel'),
            'unread_mail_count': old.get('UnReadMailCount'),
            'link_reward_date': old.get('LinkRewardDate'),
            'last_returning_date': old.get('LastReturningDate'), 'location': old.get('Location'),
        }
        updatable = dict((k, v) for k, v in updatable.items() if v is not None)
        if 'birthday' in updatable and updatable['birthday'] == SENTINEL_BIRTHDAY:
            updatable['birthday'] = None          # 哨兵 → NULL（库里 NULL 才表示未设置）
        account = self.update_account(account.server_id, **updatable) if updatable else account
        # 2) 身份修正（不重排实体 id）+ 游标推进
        self._rewrite_identity(state, account, renumber_entities=renumber_entities)
        max_seen = self._max_entity_id(state)
        if max_seen >= account.next_entity_id:
            account = self.update_account(account.server_id, next_entity_id=max_seen + 1)
        state['account'] = self.build_account_db_for(account)
        # 3) 落 blob
        with self.transaction() as conn:
            self._write_blobs(conn, account.server_id, state, updated_by=updated_by)
        return {'server_id': account.server_id, 'blobs': len(BLOB_LAYOUT),
                'next_entity_id': account.next_entity_id, 'max_entity_id_seen': max_seen}

    @staticmethod
    def _max_entity_id(state: Dict[str, Any]) -> int:
        u"""扫出状态里已用的最大实体 id（迁移后新发号不能撞它）。"""
        best = 0

        def take(v):
            nonlocal best
            if isinstance(v, int) and not isinstance(v, bool):
                best = max(best, v)

        for ch in (state.get('characters') or []):
            if isinstance(ch, dict):
                take(ch.get('ServerId'))
        for key in ('echelons', 'items', 'expiryItems', 'equipments', 'gears', 'weapons',
                    'costumes', 'emblems', 'memoryLobby'):
            for row in (state.get(key) or []):
                if isinstance(row, dict):
                    take(row.get('ServerId'))
                    take(row.get('EchelonDBId'))
        for cafe_db in (((state.get('cafe') or {}).get('cafes')) or []):
            if isinstance(cafe_db, dict):
                take(cafe_db.get('CafeDBId'))
        return best

    def _rewrite_identity(self, state: Dict[str, Any], account: Account,
                          renumber_entities: bool = True) -> None:
        u"""把状态里所有「属于别的账号」的值改成这个账号的。

        模板是单用户产物，里面有 8 处内嵌账号身份，必须逐个重写（否则第 2 个用户的咖啡馆
        AccountId 还是 1）：
          characters[].ServerId / account.RepresentCharacterServerId
          cafe.cafes[].CafeDBId、cafe.cafes[].AccountId、cafe.cafes[].ProductionDB.CafeDBId
          clan.member.AccountId、clan.member.AccountNickName
          attachment.AccountId、stickerBook.AccountId
          settings.friendCode
        renumber_entities=False 时保留 students[].ServerId（迁移已有进度时用）。
        """
        sid = account.server_id
        state['account'] = self.build_account_db_for(account)

        # --- 学生：ServerId 从本账号的实体发号游标开始，逐个递增 ---
        next_entity = int(account.next_entity_id or self.config.entity_id_base)
        chars = state.get('characters') or []
        if renumber_entities:
            for i, ch in enumerate(chars):
                if isinstance(ch, dict):
                    ch['ServerId'] = next_entity + i
            # 展示位学生 = 1 号学生（新账号还没有过 Account_SetRepresentCharacter）
            state['account']['RepresentCharacterServerId'] = next_entity if chars else 0
        else:
            # 迁移：保留原 ServerId，只保证「代表学生」确实存在
            exist = set(ch.get('ServerId') for ch in chars if isinstance(ch, dict))
            rep = state['account']['RepresentCharacterServerId']
            if rep not in exist:
                state['account']['RepresentCharacterServerId'] = (min(exist) if exist else 0)
        account.represent_character_server_id = state['account']['RepresentCharacterServerId']

        # --- 咖啡馆 ---
        cafe = state.get('cafe') or {}
        cafe_seq = next_entity + len(chars) if renumber_entities else 0
        for idx, cafe_db in enumerate(cafe.get('cafes') or []):
            if not isinstance(cafe_db, dict):
                continue
            cafe_db_id = (cafe_seq + idx) if renumber_entities else int(cafe_db.get('CafeDBId') or 1)
            cafe_db['CafeDBId'] = cafe_db_id
            cafe_db['AccountId'] = sid
            prod = cafe_db.get('ProductionDB')
            if isinstance(prod, dict):
                prod['CafeDBId'] = cafe_db_id

        # --- 公会成员影子（没加工会也存在，ClanDBId=0） ---
        clan = state.get('clan') or {}
        member = clan.get('member')
        if isinstance(member, dict):
            member['AccountId'] = sid
            member['AccountNickName'] = account.nickname or ''

        # --- 附件 / 贴纸簿 ---
        for key in ('attachment', 'stickerBook'):
            blk = state.get(key)
            if isinstance(blk, dict) and 'AccountId' in blk:
                blk['AccountId'] = sid

        # --- 好友码：8 位大写 base32（模板 "BASERVER" 也是 8 位；格式未实测，仅长度对齐） ---
        settings = state.get('settings') or {}
        if isinstance(settings, dict):
            settings['friendCode'] = self.friend_code_for(sid)

        # --- 把发号游标推到「第一个没用过的 id」：学生占 len(chars) 个，咖啡馆占 1 个 ---
        if renumber_entities:
            used = len(chars) + (1 if cafe.get('cafes') else 0)
            account.next_entity_id = next_entity + used


    @staticmethod
    def friend_code_for(server_id: int) -> str:
        digest = hashlib.sha1((u'friendCode:%d' % server_id).encode('utf-8')).digest()
        return base64.b32encode(digest).decode('ascii')[:8].upper()

    # ------------------------------------------------ 实体 id 发号
    def alloc_entity_ids(self, server_id: int, count: int = 1) -> List[int]:
        u"""发 count 个账号内唯一的实体 id（CharacterDB.ServerId / CafeDBId / ItemDB.ServerId）。"""
        count = int(count)
        if count <= 0:
            return []
        with self.transaction() as conn:
            cur = conn.cursor()
            cur.execute(self._adapt('SELECT next_entity_id FROM accounts WHERE server_id = ?'
                                    + self._for_update()), (server_id,))
            row = cur.fetchone()
            cur.close()
            if row is None:
                raise AccountServiceError(u'账号不存在: %s' % server_id)
            start = int(row['next_entity_id'] if not isinstance(row, (list, tuple)) else row[0])
            conn.cursor().execute(
                self._adapt('UPDATE accounts SET next_entity_id = ? WHERE server_id = ?'),
                (start + count, server_id))
        return list(range(start, start + count))

    # ------------------------------------------------ 运维
    def get_account(self, server_id: int) -> Optional[Account]:
        row = self._fetchone('SELECT * FROM accounts WHERE server_id = ?', (server_id,))
        return row_to_account(row) if row is not None else None

    def update_account(self, server_id: int, **fields) -> Account:
        u"""改 accounts 行的字段（协议写回的唯一入口）。返回更新后的 Account。

        典型调用：Account_Nickname(1001) 改名 → update_account(sid, nickname='新名')；
                 Account_CallName(1010) → update_account(sid, call_name='...', call_name_update_time=now)。
        只允许改白名单字段，时间字段自动 to_iso，避免拼错列名把库写坏。
        """
        if not fields:
            return self.get_account(server_id)
        sets, args = [], []
        for k, v in fields.items():
            if k not in ACCOUNT_UPDATABLE:
                raise ValueError(u'不允许更新的字段: %s（白名单: %s）'
                                 % (k, ', '.join(sorted(ACCOUNT_UPDATABLE))))
            if k in _TIME_COLUMNS:
                v = to_iso(v)
            sets.append('%s = ?' % k)
            args.append(v)
        args.append(int(server_id))
        hit = self._exec_count('UPDATE accounts SET %s WHERE server_id = ?' % ', '.join(sets), args)
        if hit == 0:
            raise AccountServiceError(u'账号不存在: %s' % server_id)
        acc = self.get_account(server_id)
        # 改名要顺带同步 blob 里的「账号影子」（公会成员列表里的昵称就是这份拷贝），
        # 否则公会界面会一直显示旧名字。失败不影响主流程。
        if 'nickname' in fields:
            self._sync_nickname_shadow(acc)
        return acc

    def _sync_nickname_shadow(self, account: Account) -> None:
        try:
            blob = self.load_blob(account.server_id, 'clan')
            member = ((blob or {}).get('clan') or {}).get('member')
            if isinstance(member, dict) and member.get('AccountNickName') != account.nickname:
                member['AccountNickName'] = account.nickname
                self.save_blob(account.server_id, 'clan', blob, updated_by=u'nickname-sync')
        except Exception:                        # noqa: BLE001
            pass

    # [PATCH-PY-20261118-sidwb] Shittim Accounts.ServerId -> accounts.shittim_server_id
    def set_shittim_server_id(self, publisher_account_id: int, shittim_server_id: int) -> bool:
        u"""把 Shittim 侧的 Accounts.ServerId 记到 accounts.shittim_server_id。

        参数 publisher_account_id 是 publisherId（accounts.publisher_account_id），
        不是 accounts.server_id：桥只解析得出 publisherId。多行命中时取 server_id 最小那行。

        幂等：现值为 NULL 或与传入值不同才 UPDATE，同值直接返回 False（不产生写）。
        返回值 = 真的发生了 UPDATE。**任何异常一律吞掉返回 False** —— 这是登录主链上的
        旁路写，宁可丢这一条也不能把登录搞挂。

        连接：沿用 self._conn()（thread-local，与 update_account 同一根连接），不新开连接，
        也不改 journal_mode（_connect() 建连时已经 WAL + busy_timeout=5000）。
        """
        try:
            pub = int(publisher_account_id or 0)
            sid = int(shittim_server_id or 0)
        except Exception:                        # noqa: BLE001
            return False
        if pub <= 0 or sid <= 0:
            return False
        try:
            row = self._fetchone(
                'SELECT server_id, shittim_server_id FROM accounts '
                'WHERE publisher_account_id = ? ORDER BY server_id LIMIT 1', (pub,))
            if row is None:
                return False
            d = _rowdict(row)
            pk = d.get('server_id')
            if pk is None:
                return False
            cur = d.get('shittim_server_id')
            if cur is not None:
                try:
                    if int(cur) == sid:
                        return False             # 幂等：同值不写
                except Exception:                # noqa: BLE001
                    pass                         # 脏值（非数字文本）留给下面覆盖掉
            hit = self._exec_count(
                'UPDATE accounts SET shittim_server_id = ? '
                'WHERE publisher_account_id = ? AND server_id = ?', (sid, pub, int(pk)))
            return hit > 0
        except Exception as e:                   # noqa: BLE001
            try:
                _warn(u'set_shittim_server_id(%r, %r) 失败: %r' % (pub, sid, e))
            except Exception:                    # noqa: BLE001
                pass
            return False

    def get_account_by_dev_id(self, dev_id: str) -> Optional[Account]:
        row = self._fetchone('SELECT * FROM accounts WHERE dev_id = ?', (dev_id,))
        return row_to_account(row) if row is not None else None

    def list_accounts(self, limit: int = 50, offset: int = 0) -> List[Account]:
        rows = self._fetchall(
            'SELECT * FROM accounts ORDER BY server_id LIMIT ? OFFSET ?', (int(limit), int(offset)))
        return [row_to_account(r) for r in rows]

    def log_protocol(self, server_id: int, protocol: int, duration_ms: int = 0,
                     resp_bytes: int = 0, status: int = 0, note: Optional[str] = None,
                     started_at: Optional[str] = None) -> None:
        u"""记一条协议流水。永远不抛（日志不该让业务失败）。"""
        try:
            self._execute(
                'INSERT INTO protocol_log (server_id, protocol, started_at, duration_ms, '
                'resp_bytes, status, note) VALUES (?,?,?,?,?,?,?)',
                (int(server_id or 0), int(protocol or 0),
                 started_at or to_iso(self.now()) + '.000',
                 int(duration_ms or 0), int(resp_bytes or 0), int(status or 0), note))
        except Exception:                        # noqa: BLE001
            pass

    def stats(self) -> Dict[str, Any]:
        def one(sql, args=()):
            row = self._fetchone(sql, args)
            if row is None:
                return 0
            v = row[0] if isinstance(row, (list, tuple)) else list(dict(row).values())[0]
            return 0 if v is None else int(v)      # MIN/MAX 在空表上返回 NULL
        out = {
            'accounts': one('SELECT COUNT(*) FROM accounts'),
            'sessions': one('SELECT COUNT(*) FROM sessions'),
            'sessions_active': one('SELECT COUNT(*) FROM sessions WHERE revoked = 0'),
            'blobs': one('SELECT COUNT(*) FROM account_blobs'),
            'protocol_log': one('SELECT COUNT(*) FROM protocol_log'),
            'server_id_min': one('SELECT MIN(server_id) FROM accounts') or 0,
            'server_id_max': one('SELECT MAX(server_id) FROM accounts') or 0,
        }
        row = self._fetchone("SELECT next_id FROM id_alloc WHERE name = 'server_id'")
        out['next_server_id'] = int(row['next_id'] if not isinstance(row, (list, tuple)) else row[0]) \
            if row else 0
        return out

    def delete_account(self, server_id: int) -> bool:
        u"""删账号（blobs / sessions 由外键 ON DELETE CASCADE 带走）。"""
        return self._exec_count('DELETE FROM accounts WHERE server_id = ?', (server_id,)) > 0

    def wipe(self, confirm: bool = False, reset_allocator: bool = True) -> Dict[str, int]:
        u"""清库（回滚用）：按子表→主表顺序删，再把发号器拨回基数。"""
        if not confirm:
            raise AccountServiceError(u'wipe() 需要 confirm=True')
        counts = {}
        with self.transaction() as conn:
            for table in ('account_blobs', 'sessions', 'protocol_log', 'accounts'):
                cur = conn.cursor()
                cur.execute('DELETE FROM %s' % table)
                counts[table] = cur.rowcount
                cur.close()
            if reset_allocator:
                conn.cursor().execute(
                    self._adapt('UPDATE id_alloc SET next_id = ? WHERE name = ?'),
                    (self.config.server_id_base, 'server_id'))
        return counts

    # ------------------------------------------------ 自检
    def selftest(self, verbose: bool = True) -> int:
        u"""完整自检：建临时库 → 建账号 → 发会话 → 解析会话 → 读 blob → 校验 AccountDB。"""
        import tempfile
        import shutil
        steps: List[Tuple[str, bool, str]] = []
        tmpdir = tempfile.mkdtemp(prefix='ba_acct_selftest_')
        db_path = os.path.join(tmpdir, 'ba_accounts.sqlite3')

        def step(name, fn):
            try:
                detail = fn()
                steps.append((name, True, detail or ''))
                if verbose:
                    print(u'  [ok]   %-46s %s' % (name, detail or ''))
                return True
            except Exception as exc:              # noqa: BLE001
                import traceback
                steps.append((name, False, '%s: %s' % (type(exc).__name__, exc)))
                if verbose:
                    print(u'  [FAIL] %-46s %s: %s' % (name, type(exc).__name__, exc))
                    traceback.print_exc()
                return False

        svc = AccountService(Config(db_path=db_path, frozen_now='2026-11-14T12:00:00',
                                    session_ttl_seconds=30 * 86400))
        ctx: Dict[str, Any] = {}
        REQ = {
            "Protocol": "Account_Auth", "DevId": "314816420",
            "OSVersion": "Android OS 17 / API-37 (sdk 37)",
            "DeviceUniqueId": "<REDACTED_DEVID>",
            "DeviceModel": "OnePlus PLR110", "DeviceSystemMemorySize": 15104,
            "Token": "<REDACTED_TOKEN>",
            "SdkPid": "CN-BA", "SubChannel": "",
            "ResUrl": "https://static.bluearchive-cn.com/prodm39",
            "Hash": 4303557230593,
        }
        try:
            print(u'== selftest: %s (sqlite %s, db=%s)' % (
                os.path.basename(__file__), sqlite3.sqlite_version, db_path))

            if not os.path.exists(svc.config.template_path):
                out = svc.make_template()
                print(u'  [gen]  模板缺失，已从 %s 生成 %s' % (SEEDED_STATE_PATH, out))

            def s1():
                n = svc.init_schema()
                t = svc._fetchall("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                return u'%d 条 DDL，表: %s' % (n, ', '.join(_rowdict(r)['name'] for r in t))

            def s2():
                ident = svc.identify(REQ)
                assert ident.dev_id == '314816420', ident.dev_id
                assert ident.device_unique_id == '3849b23ac439a18294f6e5bfb22d87c6'
                assert ident.token == '61de1d1b7519ab1231866f74c11fcfdd1f80b210'
                assert ident.publisher_account_id == 314816420
                assert ident.protocol == 1002, ident.protocol
                assert ident.counter == 1, ident.counter
                ctx['ident'] = ident
                return u'DevId=%s duid=%s… token=%s proto=%s counter=%s（Hash 解码自洽）' % (
                    ident.dev_id, ident.device_unique_id[:8], _mask(ident.token),
                    ident.protocol, ident.counter)

            def s3():
                acc = svc.get_or_create_account(ctx['ident'])
                ctx['acc1'] = acc
                assert acc.server_id == 10000000000, acc.server_id
                assert acc.level == 1 and acc.exp == 0 and acc.state == 1
                assert acc.represent_character_server_id == 1000001, acc.represent_character_server_id
                assert acc.nickname and acc.call_name
                return u'server_id=%d nickname=%s login_count=%d' % (
                    acc.server_id, acc.nickname, acc.login_count)

            def s4():
                kinds = svc.all_blobs(ctx['acc1'].server_id)
                assert set(kinds) == set(BLOB_KINDS), sorted(set(BLOB_KINDS) ^ set(kinds))
                chars = kinds['characters']['characters']
                assert len(chars) == 3, len(chars)
                assert [c['ServerId'] for c in chars] == [1000001, 1000002, 1000003]
                assert [c['UniqueId'] for c in chars] == [10010, 10000, 10001]
                assert len(kinds['currency']['currencies']) == 28
                return u'%d 个 kind；3 学生 %s；28 货币' % (
                    len(kinds), [c['UniqueId'] for c in chars])

            def s5():
                sid = ctx['acc1'].server_id
                ident2 = svc.identify({ 'DevId': '999999999',
                    'DeviceUniqueId': '<REDACTED_DEVID>',
                    'Token': 'a' * 40, 'Hash': (1002 << 32) | 7})
                acc2 = svc.get_or_create_account(ident2)
                ctx['acc2'] = acc2
                assert acc2.server_id == 10000000001, acc2.server_id
                chars = svc.load_blob(acc2.server_id, 'characters')['characters']
                assert [c['ServerId'] for c in chars] == [1100001, 1100002, 1100003], \
                    [c['ServerId'] for c in chars]
                assert svc.load_blob(sid, 'cafe')['cafe']['cafes'][0]['AccountId'] == sid
                assert svc.load_blob(acc2.server_id, 'cafe')['cafe']['cafes'][0]['AccountId'] == acc2.server_id
                return u'第二个用户 server_id=%d，实体 id 段 %s（不与 %d 撞）' % (
                    acc2.server_id, [c['ServerId'] for c in chars], sid)

            def s6():
                sk = svc.issue_session_key(ctx['acc1'])
                ctx['sk1'] = sk
                assert sk.is_well_formed(), sk.mx_token
                assert len(sk.mx_token) == 36
                assert sk.to_dict() == {'AccountServerId': 10000000000, 'MxToken': sk.mx_token}
                return u'MxToken=%s（36 字符 GUID 小写）' % sk.mx_token

            def s7():
                acc = svc.resolve_session(ctx['sk1'].mx_token)
                assert acc is not None and acc.server_id == ctx['acc1'].server_id
                acc_upper = svc.resolve_session(ctx['sk1'].mx_token.upper())
                assert acc_upper is not None, u'大小写不敏感失败'
                acc_pad = svc.resolve_session('  %s  ' % ctx['sk1'].mx_token)
                assert acc_pad is not None, u'前后空格未容忍'
                assert svc.resolve_session('00000000-0000-0000-0000-000000000000') is None
                assert svc.resolve_session('') is None and svc.resolve_session(None) is None
                return u'小写/大写/带空格 都能解析；伪造 token 返回 None'

            def s8():
                old = ctx['sk1']
                sk2 = svc.issue_session_key(ctx['acc1'], note=u'second-login')
                assert svc.resolve_session(old.mx_token) is None, u'旧会话没被顶掉'
                assert svc.resolve_session(sk2.mx_token) is not None
                ctx['sk1b'] = sk2
                return u'顶号生效（max_active_sessions=1）：旧 token 立即失效'

            def s9():
                tok = ctx['sk1b'].mx_token
                svc._execute('UPDATE sessions SET expires_at = ? WHERE mx_token = ?',
                             ('2020-01-01T00:00:00', tok))
                assert svc.resolve_session(tok) is None, u'过期会话仍然可用'
                sk3 = svc.issue_session_key(ctx['acc1'], ttl_seconds=60)
                svc._execute('UPDATE sessions SET expires_at = ? WHERE mx_token = ?',
                             (to_iso(svc.now() + timedelta(seconds=30)), sk3.mx_token))
                assert svc.resolve_session(sk3.mx_token) is not None
                ctx['sk'] = sk3
                return u'过期即失效；未过期的仍可用'

            def s10():
                db = svc.build_account_db_for(ctx['acc1'])
                assert list(db.keys()) == ACCOUNT_DB_FIELDS, list(db.keys())
                assert db['ServerId'] == 10000000000
                assert db['BirthDay'] == SENTINEL_BIRTHDAY, db['BirthDay']
                assert db['LinkRewardDate'] is None and db['LastReturningDate'] is None
                assert isinstance(db['RetentionDays'], int) and isinstance(db['VIPLevel'], int)
                assert isinstance(db['CreateDate'], str) and 'T' in db['CreateDate']
                for k in ('CreateDate', 'LastConnectTime', 'CallNameUpdateTime', 'BirthDay'):
                    assert re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', db[k]), (k, db[k])
                return u'22 字段齐、顺序一致、时间全是无时区 ISO（%s）' % db['CreateDate']

            def s11():
                state = svc.build_state_for(ctx['acc1'])
                svc.check_template(state)
                assert state['account']['ServerId'] == 10000000000
                assert len(state['characters']) == 3
                assert state['attachment']['AccountId'] == 10000000000
                assert state['stickerBook']['AccountId'] == 10000000000
                assert len(state['settings']['friendCode']) == 8
                assert state['_meta']['frozenTime'] == '2026-11-14T12:00:00'
                assert set(state) - {'_meta'} == set(STATE_KEYS)
                return u'41 状态键齐全，AccountId 全部 = %d，friendCode=%s' % (
                    state['account']['ServerId'], state['settings']['friendCode'])

            def s12():
                sid = ctx['acc1'].server_id
                blob = svc.load_blob(sid, 'items')
                assert blob == {'items': [], 'expiryItems': []}, blob
                payload = {'items': [{'ServerId': 2000001, 'UniqueId': 1, 'StackCount': 5}],
                           'expiryItems': []}
                rev = svc.save_blob(sid, 'items', payload, updated_by=u'selftest')
                assert rev == 2, rev
                assert svc.load_blob(sid, 'items') == payload
                rev2 = svc.save_blob(sid, 'items', payload, expected_revision=rev)
                assert rev2 == rev + 1
                try:
                    svc.save_blob(sid, 'items', payload, expected_revision=1)
                    raise AssertionError(u'乐观锁没生效')
                except BlobConflict:
                    pass
                try:
                    svc.save_blob(sid, 'items', {'bogusKey': 1})
                    raise AssertionError(u'未知状态块没被拒')
                except ValueError:
                    pass
                try:
                    svc.load_blob(sid, 'nope')
                    raise AssertionError(u'未知 kind 没被拒')
                except ValueError:
                    pass
                assert svc.load_blob(sid, 'items') == payload, u'冲突失败时不该写坏数据'
                return u'revision 1→2→3；旧 revision 报 BlobConflict；未知 kind/键被拒'

            def s13():
                before = ctx['acc1'].login_count
                acc = svc.get_or_create_account(ctx['ident'])
                assert acc.login_count == before + 1, (before, acc.login_count)
                assert acc.last_login_at == '2026-11-14T12:00:00'
                assert svc.get_account(acc.server_id).dev_id == '314816420'
                return u'login_count %d→%d，last_login_at=%s（无时区）' % (
                    before, acc.login_count, acc.last_login_at)

            def s14():
                ids = svc.alloc_entity_ids(ctx['acc1'].server_id, 2)
                assert ids == [1000005, 1000006], ids
                ids2 = svc.alloc_entity_ids(ctx['acc2'].server_id, 1)
                assert ids2 == [1100005], ids2
                return u'实体发号 %s / %s（学生占 1000001-3、咖啡馆占 1000004，游标已推进）' % (ids, ids2)

            def s15():
                svc.log_protocol(10000000000, 1002, 12, 3164)
                svc.log_protocol(10000000000, 1017, 40, 51200, status=0, note=u'login-sync')
                st = svc.stats()
                assert st['accounts'] == 2, st
                assert st['protocol_log'] == 2, st
                assert st['next_server_id'] == 10000000002, st
                return u'accounts=%d blobs=%d sessions=%d log=%d next_id=%d' % (
                    st['accounts'], st['blobs'], st['sessions'], st['protocol_log'],
                    st['next_server_id'])

            def s16():
                sid = ctx['acc2'].server_id
                assert svc.delete_account(sid) is True
                assert svc.get_account(sid) is None
                assert svc.all_blobs(sid) == {}, u'blob 没被级联删掉'
                assert svc.list_sessions(sid) == []
                assert svc.get_account(ctx['acc1'].server_id) is not None, u'误删了别的账号'
                return u'删 %d 后 blobs/sessions 级联清空，另一个账号完好' % sid

            def s17():
                tmpl = svc._template()
                svc.check_template(tmpl)
                assert len(STATE_KEYS) == 41, len(STATE_KEYS)
                assert len(BLOB_KINDS) == 21, len(BLOB_KINDS)
                return u'模板 %d 状态键 → 1 行 + %d 个 blob kind' % (len(STATE_KEYS), len(BLOB_KINDS))

            def s18():
                sid = ctx['acc1'].server_id
                acc = svc.update_account(sid, nickname=u'新老师', call_name=u'老师',
                                         call_name_update_time='2026-11-14T12:00:00')
                assert acc.nickname == u'新老师', acc.nickname
                assert svc.build_account_db_for(acc)['Nickname'] == u'新老师'
                assert svc.build_state_for(acc)['clan']['member']['AccountNickName'] == u'新老师', \
                    u'公会影子昵称没跟着改'
                try:
                    svc.update_account(sid, dev_id='<REDACTED_DEVID>')
                    raise AssertionError(u'白名单外的字段没被拒')
                except ValueError:
                    pass
                return u'改名落库并可回读；dev_id 不在白名单（换设备=换号）'

            def s19():
                if not os.path.exists(SEEDED_STATE_PATH):
                    return u'跳过：找不到 %s（迁移路径需要 proto 资产）' % SEEDED_STATE_PATH
                with open(SEEDED_STATE_PATH, 'r', encoding='utf-8') as f:
                    seeded = json.load(f)
                acc3 = svc.get_or_create_account(Identity(dev_id='<REDACTED_DEVID>',
                                                          publisher_account_id=123))
                before = acc3.next_entity_id
                summary = svc.import_state(acc3, seeded, updated_by=u'selftest:import')
                acc3 = svc.get_account(acc3.server_id)     # import 之后必须重读（勿用旧对象）
                st = svc.build_state_for(acc3)
                assert [c['ServerId'] for c in st['characters']] == [1000001, 1000002, 1000003], \
                    u'迁移不该重排 students[].ServerId'
                assert st['attachment']['AccountId'] == acc3.server_id, u'AccountId 没重写'
                assert st['account']['Nickname'] == seeded['account']['Nickname'], u'昵称没导入'
                assert len(st['currencies']) == 28
                assert summary['next_entity_id'] > summary['max_entity_id_seen'], summary
                assert summary['max_entity_id_seen'] == 1000003, summary
                svc.delete_account(acc3.server_id)
                return u'导入 41 键、保留 %d 个学生 ServerId、AccountId 重写、游标 %d（已越过 %d）' % (
                    len(st['characters']), summary['next_entity_id'],
                    summary['max_entity_id_seen'])

            def s20():
                legacy = 10015354380                     # 现有硬编码的真账号号段
                acc4 = svc.create_account_at(Identity(dev_id='<REDACTED_DEVID>',
                                                      publisher_account_id=314816420), legacy)
                assert acc4.server_id == legacy, acc4.server_id
                assert acc4.nickname.startswith(svc.config.nickname_prefix), acc4.nickname
                nxt = svc.stats()['next_server_id']
                assert nxt == legacy + 1, (nxt, legacy)
                acc5 = svc.get_or_create_account(Identity(dev_id='<REDACTED_DEVID>'))
                assert acc5.server_id == legacy + 1, acc5.server_id
                assert svc.get_account(legacy).nickname == acc4.nickname
                svc.delete_account(acc4.server_id)
                svc.delete_account(acc5.server_id)
                return u'按指定号建 %d、发号器推到 %d、下一个新号 %d（不撞）' % (
                    legacy, nxt, acc5.server_id)

            for name, fn in [
                (u'1 建库（schema_sqlite.sql）', s1),
                (u'2 identify(实测 Account_Auth 请求体)', s2),
                (u'3 get_or_create_account（首个账号）', s3),
                (u'4 初始状态：3 学生 / 28 货币 / 21 blobs', s4),
                (u'5 第二个用户独立（id 段不撞）', s5),
                (u'6 issue_session_key', s6),
                (u'7 resolve_session（大小写不敏感）', s7),
                (u'8 顶号：旧 MxToken 立即失效', s8),
                (u'9 会话过期', s9),
                (u'10 build_account_db_for（22 字段）', s10),
                (u'11 build_state_for（41 键）', s11),
                (u'12 load_blob / save_blob / 乐观锁', s12),
                (u'13 登录记账（login_count）', s13),
                (u'14 alloc_entity_ids', s14),
                (u'15 protocol_log / stats', s15),
                (u'16 delete_account（级联）', s16),
                (u'17 模板与 21 kind 布局自洽', s17),
                (u'18 update_account（改名落库）', s18),
                (u'19 import_state（迁移现有状态）', s19),
                (u'20 create_account_at（保留历史 server_id）', s20),
            ]:
                if not step(name, fn):
                    break

            total = 20
            ok = all(ok_ for _, ok_, _ in steps) and len(steps) == total
            print(u'== selftest: %d/%d 通过%s ==' % (
                sum(1 for _, o, _ in steps if o), total, u'' if ok else u' —— 有失败'))
            if ok:
                print(u'== 核心链路: 建账号 → 发会话 → 解析会话 → 读/写 blob → AccountDB 全部跑通 ==')
            return 0 if ok else 1
        finally:
            svc.close()
            shutil.rmtree(tmpdir, ignore_errors=True)

    # ------------------------------------------------ 模板生成
    def make_template(self, src: Optional[str] = None, out: Optional[str] = None) -> str:
        u"""从 proto/account_state.seeded.json 派生新账号模板（只重写 _meta，状态块原样保留）。"""
        src = src or SEEDED_STATE_PATH
        out = out or self.config.template_path
        if not os.path.exists(src):
            raise TemplateMissing(u'找不到源状态文件: %s' % src)
        with open(src, 'rb') as f:
            raw = f.read()
        seeded = json.loads(raw.decode('utf-8'))
        src_meta = seeded.get(META) or {}
        state = dict((k, v) for k, v in seeded.items() if not k.startswith('_'))
        self.check_template(state)
        meta = {
            'model': 'account_template',
            'version': 1,
            'role': u'多用户账号服务的新账号初始状态模板：bootstrap_state() 深拷贝它，再重写 8 处身份字段',
            'source': {
                'path': os.path.abspath(src),
                'bytes': len(raw),
                'sha256': hashlib.sha256(raw).hexdigest(),
                'seededFrozenTime': src_meta.get('frozenTime'),
            },
            'frozenTime': src_meta.get('frozenTime') or '2026-11-14T00:00:00',
            'stateKeys': len(STATE_KEYS),
            'blobKinds': BLOB_KINDS,
            'rowBackedKeys': list(ROW_BACKED_KEYS),
            'semantics': u'刚建号但未改名的国服账号：Level=1 / Exp=0 / 3 个 1 级学生 / 28 种货币 / 无道具无编队无通关',
            'notRewritten': [u'cafe.cafes[].CafeId', u'cafe.cafes[].CafeRank', u'auth.EncryptedUID',
                             u'auth.CurrentVersion', u'auth.TTSCdnUri'],
            'note': u'本文件的 account 块与 characters[].ServerId 只是占位，运行时会被 '
                    u'_rewrite_identity() 覆盖。改初始值只影响**之后新建**的账号；'
                    u'已存在的账号请直接改 account_blobs.payload（本服务不提供 rebootstrap），'
                    u'因为重排 Student ServerId 会打断已有进度。',
        }
        doc = {META: meta}
        doc.update(state)
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write('\n')
        return out


# ---------------------------------------------------------------- 行 ↔ 对象
def _rowdict(row) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    try:
        return dict((k, row[k]) for k in row.keys())
    except Exception:                            # noqa: BLE001
        return dict(row)


_TIMEOUT_COLUMNS = ('issued_at', 'expires_at', 'last_seen', 'created_at', 'last_login_at',
                    'token_seen_at', 'birthday', 'call_name_update_time', 'link_reward_date',
                    'last_returning_date')
_TIME_COLUMNS = frozenset(_TIMEOUT_COLUMNS)

# update_account() 允许写的列（身份列 server_id / dev_id 不在白名单：换设备等于换号）
ACCOUNT_UPDATABLE = frozenset([
    'device_unique_id', '<REDACTED_DEVID>', 'publisher_account_id', 'nickname', 'call_name', 'state',
    'level', 'exp', 'comment', 'lobby_mode', 'represent_character_server_id',
    'memory_lobby_unique_id', 'location', 'birthday', 'call_name_update_time',
    'link_reward_date', 'last_returning_date', 'retention_days', 'vip_level',
    'unread_mail_count', 'next_entity_id',
])


def row_to_account(row) -> Account:
    d = _rowdict(row)
    for col in _TIMEOUT_COLUMNS:
        if col in d:
            d[col] = to_iso(d[col])
    fields = set(Account.__dataclass_fields__)
    return Account(**dict((k, v) for k, v in d.items() if k in fields))


def _is_unique_violation(exc: Exception) -> bool:
    if isinstance(exc, sqlite3.IntegrityError):
        return 'UNIQUE' in str(exc).upper() or 'PRIMARY KEY' in str(exc).upper()
    return type(exc).__name__ in ('IntegrityError', 'IntegrityError_') and \
        'duplicate' in str(exc).lower()


def _decode_request(req: Any) -> Tuple[Dict[str, Any], Optional[int], Optional[int]]:
    u"""请求 → (body, protocol, counter)。Hash = (protocol << 32) | counter。"""
    if isinstance(req, (bytes, bytearray)):
        body = json.loads(req.decode('utf-8-sig'))
    elif isinstance(req, str):
        body = json.loads(req)
    elif isinstance(req, dict):
        body = req
    else:
        raise TypeError(u'req 需要 dict / JSON str / bytes，实得 %s' % type(req).__name__)
    if not isinstance(body, dict):
        raise TypeError(u'请求体不是 JSON 对象')

    protocol = body.get('Protocol')
    if isinstance(protocol, str):
        protocol = int(protocol) if protocol.isdigit() else None
    elif not isinstance(protocol, int):
        protocol = None
    counter = None
    h = body.get('Hash')
    if isinstance(h, int) and h >= 0:
        if protocol is None:
            protocol = h >> 32
        counter = h & 0xFFFFFFFF
    return body, protocol, counter


def _pick(body: Dict[str, Any], names: Iterable[str]) -> Any:
    u"""按名字取值：先精确、再大小写不敏感，最后往嵌套对象里看一层（容忍外面包一层 DTO）。"""
    for n in names:
        if n in body:
            return body[n]
    lower = dict((str(k).lower(), k) for k in body)
    for n in names:
        k = lower.get(n.lower())
        if k is not None:
            return body[k]
    for k, v in body.items():
        if isinstance(v, dict):
            for n in names:
                if n in v:
                    return v[n]
    return None


def split_sql(text: str) -> List[str]:
    u"""按 ';' 切 SQL：先剥掉 -- 行注释和 /* */ 块注释（DDL 里没有存储过程，够用）。"""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    text = re.sub(r'--[^\n]*', '', text)
    return [chunk.strip() for chunk in text.split(';') if chunk.strip()]


# ---------------------------------------------------------------- 模块级默认实例（对外契约那 7 个函数）
_DEFAULT_LOCK = threading.Lock()
_DEFAULT_SERVICE: Optional[AccountService] = None


def default_service(config: Optional[Config] = None) -> AccountService:
    global _DEFAULT_SERVICE
    with _DEFAULT_LOCK:
        if config is not None:
            _DEFAULT_SERVICE = AccountService(config)
        elif _DEFAULT_SERVICE is None:
            _DEFAULT_SERVICE = AccountService(Config.from_env())
        return _DEFAULT_SERVICE


def configure(**kwargs) -> AccountService:
    u"""换掉默认实例（网关启动时调用一次）：configure(db_path=..., dialect='mysql', ...)。"""
    return default_service(Config.from_env(**kwargs))


def identify(req) -> Identity:
    return default_service().identify(req)


def get_or_create_account(identity: Identity, record_login: bool = True) -> Account:
    return default_service().get_or_create_account(identity, record_login=record_login)


def issue_session_key(account: Account, client_ip: Optional[str] = None,
                      note: Optional[str] = None,
                      ttl_seconds: Optional[int] = None) -> SessionKey:
    return default_service().issue_session_key(account, client_ip=client_ip, note=note,
                                               ttl_seconds=ttl_seconds)


def resolve_session(mx_token, touch: Optional[bool] = None) -> Optional[Account]:
    return default_service().resolve_session(mx_token, touch=touch)


def load_blob(server_id: int, kind: str) -> Optional[Dict[str, Any]]:
    return default_service().load_blob(server_id, kind)


def save_blob(server_id: int, kind: str, payload: Dict[str, Any],
              expected_revision: Optional[int] = None,
              updated_by: Optional[str] = None) -> int:
    return default_service().save_blob(server_id, kind, payload, expected_revision=expected_revision,
                                       updated_by=updated_by)


def build_account_db_for(account: Account) -> Dict[str, Any]:
    return default_service().build_account_db_for(account)


def build_state_for(account: Account, **kwargs) -> Dict[str, Any]:
    return default_service().build_state_for(account, **kwargs)


def bootstrap_state(account: Account) -> Dict[str, Any]:
    return default_service().bootstrap_state(account)


def alloc_entity_ids(server_id: int, count: int = 1) -> List[int]:
    return default_service().alloc_entity_ids(server_id, count)


# ---------------------------------------------------------------- CLI
def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8')     # Windows 控制台默认 GBK
    except Exception:                                # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(
        description=u'国服蔚蓝档案私服 · 多用户账号服务（schema + 服务层自检/运维）')
    ap.add_argument('--selftest', action='store_true', help=u'建临时库跑全套自检')
    ap.add_argument('--init-db', action='store_true', help=u'执行 DDL 建库建表')
    ap.add_argument('--make-template', action='store_true', help=u'从 proto/account_state.seeded.json 生成模板')
    ap.add_argument('--template-src', default=None)
    ap.add_argument('--stats', action='store_true', help=u'看库里的账号/会话/blob 计数')
    ap.add_argument('--list-kinds', action='store_true', help=u'打印 blob kind ↔ 状态块布局')
    ap.add_argument('--dump-state', action='store_true', help=u'导出某账号的完整 41 键状态 JSON')
    ap.add_argument('--import-state', default=None,
                    help=u'把一份 account_state JSON 灌进账号（迁移现有硬编码状态用）')
    ap.add_argument('--dev-id', default=None, help=u'配合 --import-state：按 dev_id 建号/找号')
    ap.add_argument('--force-server-id', type=int, default=None,
                    help=u'配合 --import-state：按指定 server_id 建号（迁移历史账号、保住存档前缀）')
    ap.add_argument('--server-id', type=int, default=None)
    ap.add_argument('--db', default=None, help=u'sqlite 文件路径，或 mysql 库名')
    ap.add_argument('--dialect', default=None, choices=['sqlite', 'mysql'])
    ap.add_argument('--server-id-base', type=int, default=None)
    ap.add_argument('--frozen-now', default=None, help=u'固定「现在」（测试用，如 2026-11-14T12:00:00）')
    ap.add_argument('--out', default=None)
    ap.add_argument('-q', '--quiet', action='store_true')
    a = ap.parse_args(argv)

    if a.list_kinds:
        print(u'%-14s %s' % (u'blob kind', u'覆盖的状态块（build_response.py 用的 41 键）'))
        for kind, keys in BLOB_LAYOUT.items():
            print(u'%-14s %s' % (kind, ', '.join(keys)))
        print(u'\n共 %d 个 kind / %d 个状态块；另有 account 走 accounts 行'
              % (len(BLOB_LAYOUT), len(STATE_KEYS) - 1))
        return 0

    overrides: Dict[str, Any] = {}
    if a.dialect:
        overrides['dialect'] = a.dialect
    if a.server_id_base:
        overrides['server_id_base'] = a.server_id_base
    if a.frozen_now:
        overrides['frozen_now'] = a.frozen_now
    cfg = Config.from_env(**overrides)
    if a.db:
        if cfg.dialect == 'mysql':
            cfg.mysql_database = a.db
        else:
            cfg.db_path = a.db

    if a.selftest:
        return AccountService(Config()).selftest()
    if a.make_template:
        svc = AccountService(cfg)
        out = svc.make_template(a.template_src, a.out)
        print(u'wrote %s' % out)
        return 0
    if a.init_db:
        svc = AccountService(cfg)
        n = svc.init_schema(verbose=not a.quiet)
        target = cfg.mysql_database if cfg.dialect == 'mysql' else cfg.db_path
        print(u'DDL 执行 %d 条 -> %s（%s）' % (n, target, cfg.dialect))
        print(u'stats: %s' % json.dumps(svc.stats(), ensure_ascii=False))
        return 0
    if a.stats:
        svc = AccountService(cfg)
        print(json.dumps(svc.stats(), ensure_ascii=False, indent=2))
        return 0
    if a.import_state:
        if not (a.dev_id or a.server_id):
            print(u'--import-state 需要 --dev-id 或 --server-id 指定灌给谁', file=sys.stderr)
            return 2
        svc = AccountService(cfg)
        if a.server_id is not None:
            target = svc.get_account(a.server_id)
            if target is None:
                print(u'没有这个账号: %s' % a.server_id, file=sys.stderr)
                return 2
        else:
            target = svc.get_account_by_dev_id(a.dev_id)
            if target is None:
                pub = int(a.dev_id) if str(a.dev_id).isdigit() else 0
                ident = Identity(dev_id=a.dev_id, publisher_account_id=pub)
                if a.force_server_id:
                    target = svc.create_account_at(ident, a.force_server_id)
                    print(u'按指定号新建账号 %s（dev_id=%s）' % (target.server_id, target.dev_id))
                else:
                    target = svc.get_or_create_account(ident)
                    print(u'新建账号 %s（dev_id=%s）' % (target.server_id, target.dev_id))
        with open(a.import_state, 'r', encoding='utf-8-sig') as f:
            state = json.load(f)
        summary = svc.import_state(target, state, updated_by=u'import:%s'
                                  % os.path.basename(a.import_state))
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(u'stats: %s' % json.dumps(svc.stats(), ensure_ascii=False))
        return 0
    if a.dump_state:
        if a.server_id is None:
            print(u'--dump-state 需要 --server-id', file=sys.stderr)
            return 2
        svc = AccountService(cfg)
        acc = svc.get_account(a.server_id)
        if acc is None:
            print(u'没有这个账号: %s' % a.server_id, file=sys.stderr)
            return 2
        state = svc.build_state_for(acc)
        text = json.dumps(state, ensure_ascii=False, indent=2)
        if a.out:
            with open(a.out, 'w', encoding='utf-8') as f:
                f.write(text + '\n')
            print(u'wrote %s' % a.out)
        else:
            print(text)
        return 0

    ap.print_help()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except AccountServiceError as _ex:
        try:
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:                        # noqa: BLE001
            pass
        print(u'error: %s' % _ex, file=sys.stderr)
        sys.exit(4)
