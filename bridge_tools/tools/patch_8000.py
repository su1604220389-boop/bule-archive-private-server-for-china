#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_8000.py —— 给 bridge 打 Mission_List (8000) 补丁。

它做三件事（全部幂等）：
  1. 在 bridge 模块级插入一个 **managed block**（BEGIN/END 标记），
     里面是目录驱动的 8000 生成逻辑 + 运行时读取的**独立开关文件**；
  2. 把 `if num == 8000:` 分支体换成「调 managed block → 发送」；
  3. 部署两个数据文件到 bridge 同目录：
       <catalog>  任务目录（gen8000.py --emit-catalog 产出，7153 条 / 144 KB）
       <switch>   独立开关（改这个文件即生效，不用重新打补丁/重启）

规则
────
  · 只改 --target 指定的那一个文件；数据文件单独备份；
  · 每次真正改动前都先备份 `target.bak.<TS>`（同秒不覆盖）；
  · 已打过且内容一致 ⇒ **逐字节 no-op**（不产生新备份、不改 mtime）；
  · 改完立刻 `compile()` 语法检查，失败就回滚并报错，绝不留半成品；
  · 不联网、不连服务器、不 import bridge（bridge 依赖服务器环境）。

模式
────
  (默认 --apply)   打好补丁
  --dry-run        只打印 diff 与将要写入的文件，一个字节都不写
  --verify         语法 + 标记配对 + 分支委托 + 开关文件 + 渲染一次 + spec_check
  --rollback       从最新的 `target.bak.<TS>` 还原
  --status         当前状态（块在不在、开关注、目录几条、备份几个）
  --enable / --disable   只翻开关文件，不碰源码（最快的失灵开关）

用法（本地演练）
────────────────
  python patch_8000.py --target C:\\tmp\\account_auth_probe.py --dry-run
  python patch_8000.py --target C:\\tmp\\account_auth_probe.py
  python patch_8000.py --target C:\\tmp\\account_auth_probe.py --verify
  python patch_8000.py --target C:\\tmp\\account_auth_probe.py --rollback

用法（服务器，确认目标路径后再执行）
────────────────────────────────────
  python3 /www/wwwroot/bapatch/deploy/patch_8000.py \\
      --target /www/wwwroot/bapatch/tools/account_auth_probe.py --dry-run
  python3 /www/wwwroot/bapatch/deploy/patch_8000.py \\
      --target /www/wwwroot/bapatch/tools/account_auth_probe.py
  python3 /www/wwwroot/bapatch/deploy/patch_8000.py \\
      --target /www/wwwroot/bapatch/tools/account_auth_probe.py --verify
  # 出问题立刻软关（不用还原源码）
  python3 /www/wwwroot/bapatch/deploy/patch_8000.py \\
      --target /www/wwwroot/bapatch/tools/account_auth_probe.py --disable
  # 彻底还原
  python3 /www/wwwroot/bapatch/deploy/patch_8000.py \\
      --target /www/wwwroot/bapatch/tools/account_auth_probe.py --rollback

与 scripts/292_24000_official.py 的关系
──────────────────────────────────────
  完全同构（同样的 BEGIN/END + 分支替换 + cn_wire.wrap_response + 备份/回滚），
  只是目标协议从 24000 换成 8000，数据从「单文件模板」换成「目录 + 开关」。
  两个补丁互不干扰：它们只碰各自的 `if num == <proto>:` 分支和各自的 block。
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
# deploy → server → ba → work → BAServer
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))

# 本文件会 import 同目录的 gen8000 来现算目录；别在 deploy/ 里留 __pycache__
sys.dont_write_bytecode = True

BEGIN = '# ==== BEGIN 8000_mission_list (managed block) ===='
END = '# ==== END 8000_mission_list (managed block) ===='

# 服务器上的默认位置（只用于给默认值，脚本本身不会去连服务器）
DEFAULT_TARGET = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
DEFAULT_CATALOG_NAME = '8000_catalog.json'
DEFAULT_SWITCH_NAME = '8000_switch.json'

# gen8000.py --emit-catalog 的产物
LOCAL_CATALOG = os.path.join(HERE, DEFAULT_CATALOG_NAME)

OFFICIAL_TOP_KEYS = ['Protocol', 'SessionKey', 'ServerTimeTicks', 'ServerNotification',
                     'RequestId', 'HistoryDBs', 'ProgressDBs', 'DailySuddenMissionInfo',
                     'MissionHistoryUniqueIds', 'ClearedOriginalMissionIds']

DEFAULT_SWITCH = {
    "_comment": "Mission_List(8000) 运行时开关。改 enabled 后立刻生效，无需重启。",
    "enabled": True,
    "profile": "seed",          # seed=日/周常一批未完成；empty=进度全空
    "reset_hour": 4,            # 日重置小时（证据见 gen8000.py 文件头 §六）
    "daily_sudden_id": 1606,    # DailySuddenMissionInfo.Id
    "max_progress": 5000,       # 安全阀：单次回包最多多少条（防目录异常导致巨包）
}


# ================================================================ managed block
# 注意：这个字符串会被原样写进 bridge，所以**只能依赖标准库**，
# 且所有 import 都放在函数内（不影响 bridge 顶层命名空间）。
MANAGED_BLOCK = r'''# ==== BEGIN 8000_mission_list (managed block) ====
# Mission_List (8000) -- generated from the official capture structure.
#
# Request variant is decided by the request's EventContentId:
#     EventContentId == null  -> full list (progress driven; new account -> small)
#     EventContentId == N     -> only that event's missions (pure table driven)
# Verified against report/_tmp/official_decoded_201/{08,10,11}_8000_*.response.json:
#     EventContentId 849   -> 39 rows (official 39, set equal)
#     EventContentId 10838 -> 35 rows (official 35, set equal)
# Top-level key order and the 5 envelope fields match the official byte for byte.
#
# Runtime data (both next to this file):
#     _BA8000_CATALOG_FILE   [uid, category, event_content_id, f15, f16] x 7153
#     _BA8000_SWITCH_FILE    {"enabled": bool, "profile": ..., ...}
# Flip the switch file to disable without redeploying the bridge.
_BA8000_CATALOG_FILE = __BA8000_CATALOG__
_BA8000_SWITCH_FILE = __BA8000_SWITCH__
_BA8000_CACHE = {'key': None, 'by_uid': None, 'by_event': None}
_BA8000_SW_CFG = {'key': None, 'cfg': None}
_BA8000_DEFAULT_SWITCH = __BA8000_DEFAULT_SWITCH__

# f16 is the per-mission "progress parameter kind" slot of
# EventContentMissionDBSchema. Cross-tab on the 56 official cat-8 rows:
#     83        -> key = str(f15)
#     121 / 122 -> key = str(EventContentId)
#     3   / 131 -> no ProgressParameters at all ({})
# That rule reproduces the official 56/56 (see gen8000.py --selfcheck 5).
_BA8000_PP_NONE = (3, 131)
_BA8000_PP_ECI = (121, 122)


def _ba8000_switch():
    """Independent switch file; a missing/corrupt file falls back to defaults."""
    import os as _os
    import json as _json
    try:
        st = _os.stat(_BA8000_SWITCH_FILE)
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        return dict(_BA8000_DEFAULT_SWITCH)
    if _BA8000_SW_CFG['cfg'] is not None and _BA8000_SW_CFG['key'] == key:
        return _BA8000_SW_CFG['cfg']
    cfg = dict(_BA8000_DEFAULT_SWITCH)
    try:
        with open(_BA8000_SWITCH_FILE, 'r', encoding='utf-8') as fh:
            raw = _json.load(fh)
        if isinstance(raw, dict):
            cfg.update(raw)
    except Exception:
        pass
    _BA8000_SW_CFG['key'] = key
    _BA8000_SW_CFG['cfg'] = cfg
    return cfg


def _ba8000_catalog():
    """Lazy-load the mission catalog, re-reading only when the file changes."""
    import os as _os
    import json as _json
    try:
        st = _os.stat(_BA8000_CATALOG_FILE)
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        return None
    if _BA8000_CACHE['by_uid'] is not None and _BA8000_CACHE['key'] == key:
        return _BA8000_CACHE
    by_uid = {}
    by_event = {}
    with open(_BA8000_CATALOG_FILE, 'r', encoding='utf-8') as fh:
        doc = _json.load(fh)
    for row in doc.get('rows') or ():
        uid = int(row[0])
        m = (uid, int(row[1]), int(row[2]) or None,
             int(row[3]) if len(row) > 3 and int(row[3]) else None,
             int(row[4]) if len(row) > 4 and int(row[4]) else None)
        by_uid[uid] = m
        if m[2] is not None:
            by_event.setdefault(m[2], []).append(m)
    for ev in by_event:
        by_event[ev].sort(key=lambda x: x[0])
    _BA8000_CACHE['key'] = key
    _BA8000_CACHE['by_uid'] = by_uid
    _BA8000_CACHE['by_event'] = by_event
    return _BA8000_CACHE


def _ba8000_pp(m):
    """ProgressParameters for one mission. New accounts: value always 0."""
    uid, cat, ev, f15, f16 = m
    if cat == 8:
        if f16 in _BA8000_PP_NONE:
            return {}
        if f16 in _BA8000_PP_ECI:
            return {str(ev): 0} if ev is not None else {}
        if f15 is not None:
            return {str(f15): 0}
        return {str(ev): 0} if ev is not None else {}
    if cat == 7:
        # The official cat-7 key looks like 110838101 and hits
        # MiniGameDefenseStageDBSchema.Id; the mission->stage mapping is NOT known,
        # so fall back to EventContentId (6/18 identical to the official).
        return {str(ev): 0} if ev is not None else {}
    return {"0": 0}


def _ba8000_start_date(account_id, hour):
    """Pinned to the current daily reset + an account-derived offset.

    Deterministic for the whole day => two calls in a row return the same bytes
    (ServerTimeTicks / RequestId aside), which is what a repeatedly-polled
    lobby protocol needs. Mirrors the official shape 2026-11-16T04:00:06.215.
    """
    import hashlib as _hl
    import struct as _st
    import datetime as _dt
    now = _dt.datetime.utcnow()
    r = now.replace(hour=int(hour) % 24, minute=0, second=0, microsecond=0)
    if now < r:
        r -= _dt.timedelta(days=1)
    h = _hl.sha256(b'ba8000:startdate:%d' % int(account_id)).digest()
    ms = 1000 + _st.unpack_from('>I', h, 0)[0] % 20000
    r += _dt.timedelta(milliseconds=ms)
    return '%04d-%02d-%02dT%02d:%02d:%02d.%03d' % (
        r.year, r.month, r.day, r.hour, r.minute, r.second, r.microsecond // 1000)


def _ba8000_net_ticks():
    """.NET 100ns ticks since 0001-01-01 (same unit as the official 24000/8000)."""
    import datetime as _dt
    d = _dt.datetime.utcnow() - _dt.datetime(1, 1, 1)
    return (d.days * 86400 + d.seconds) * 10000000 + d.microseconds * 10


def _ba8000_pick_progress(cfg, cat, account_id, event_content_id, start_date):
    """Return the ProgressDBs list for this request variant."""
    cap = int(cfg.get('max_progress') or 5000)

    # ---- event variant: pure table driven, identical to the official set
    if event_content_id is not None:
        ms = (cat['by_event'] or {}).get(int(event_content_id)) or []
        out = []
        for m in ms[:cap]:
            item = {'AccountServerId': int(account_id),
                    'MissionUniqueId': m[0],
                    'Category': m[1],
                    'StartDate': start_date,
                    'ProgressParameters': _ba8000_pp(m)}
            out.append(item)
        return out, 'event'

    profile = (cfg.get('profile') or 'seed').lower()
    if profile == 'empty':
        return [], 'full-empty'

    # ---- full variant, seed profile: the time-driven daily / weekly records.
    # These are created by the 04:00 reset job regardless of account progress
    # (all official cat1/2/9/10 rows share StartDate 2026-11-16T04:00:06.215),
    # everything else needs real progress -> left out for a new account.
    by_uid = cat['by_uid'] or {}
    picked = []
    for m in by_uid.values():
        if m[1] == 1 and 1500 <= m[0] <= 1514:
            picked.append(m)
        elif m[1] == 2 and 2300 <= m[0] <= 2400:
            picked.append(m)
    for want_cat, want_uid in ((9, int(cfg.get('daily_sudden_id') or 1606)), (10, 1701)):
        m = by_uid.get(want_uid)
        if m is not None and m[1] == want_cat:
            picked.append(m)
    picked.sort(key=lambda x: x[0])
    seen = set()
    out = []
    for m in picked:
        if m[0] in seen:
            continue
        seen.add(m[0])
        out.append({'AccountServerId': int(account_id),
                    'MissionUniqueId': m[0],
                    'Category': m[1],
                    'StartDate': start_date,
                    'ProgressParameters': _ba8000_pp(m)})
        if len(out) >= cap:
            break
    return out, 'full-seed'


def _ba8000_build(frag, rec):
    """Build the Mission_List(8000) inner object from the decrypted request."""
    import uuid as _uuid
    if not isinstance(frag, dict):
        frag = {}
    cfg = _ba8000_switch()
    sk = frag.get('SessionKey') or {}
    account_id = frag.get('AccountId') or sk.get('AccountServerId') or 0
    mx_token = sk.get('MxToken') or ''
    eci = frag.get('EventContentId')
    try:
        eci = int(eci) if eci is not None else None
    except (TypeError, ValueError):
        eci = None

    cat = _ba8000_catalog()
    progress = []
    variant = 'catalog-missing'
    if cat is not None:
        start_date = _ba8000_start_date(account_id, cfg.get('reset_hour') or 4)
        progress, variant = _ba8000_pick_progress(cfg, cat, account_id, eci, start_date)

    obj = {
        'Protocol': 8000,
        'SessionKey': {'AccountServerId': int(account_id), 'MxToken': mx_token},
        'ServerTimeTicks': _ba8000_net_ticks(),
        'ServerNotification': 0,
        'RequestId': str(_uuid.uuid4()),
        # the official sends null here in 3/3 captures -- do not fill an array
        'HistoryDBs': None,
        'ProgressDBs': progress,
        'DailySuddenMissionInfo': {'Id': int(cfg.get('daily_sudden_id') or 1606)},
        # player clear history: empty for a new account
        'MissionHistoryUniqueIds': [],
        'ClearedOriginalMissionIds': [],
    }
    if rec is not None:
        rec['gen_kind'] = 'official-8000'
        rec['ba8000_variant'] = variant
        rec['ba8000_event_content_id'] = eci
        rec['ba8000_progress'] = len(progress)
        rec['ba8000_switch'] = bool(cfg.get('enabled'))
    return obj


def _ba8000_send(proto_name, obj, rec):
    """Same envelope as the official server: outer requestid == inner RequestId."""
    import json as _json
    import uuid as _uuid
    rid = obj.get('RequestId') or str(_uuid.uuid4())
    wire, plain, key = cn_wire.wrap_response(proto_name, obj, rid)
    rec['wrap_mode'] = 'direct_envelope'
    rec['enc_requestid'] = rid
    rec['enc_inner_keys'] = len(obj) if isinstance(obj, dict) else 0
    rec['enc_inner_bytes'] = len(_json.dumps(obj, ensure_ascii=False,
                                             separators=(',', ':')).encode('utf-8'))
    rec['enc_plain_len'] = len(plain)
    rec['enc_body_len'] = len(wire)
    rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
    return 200, wire, 'text/plain; charset=utf-8'
# ==== END 8000_mission_list (managed block) ====
'''

# 分支体：与 292_24000_official.py 同构（frag / rec / name 三个名字由 bridge 提供）
BRANCH_NEW = [
    'if num == 8000:',
    "    _ba8000_cfg = _ba8000_switch()",
    "    if not _ba8000_cfg.get('enabled', True):",
    "        rec['gen_kind'] = 'ba8000-disabled'",
    "    else:",
    "        try:",
    "            obj = _ba8000_build(frag, rec)",
    "            if rec is not None:",
    "                rec['fallback'] = 'catalog-driven'",
    "            return _ba8000_send(name or 'Mission_List', obj, rec)",
    "        except Exception as _ba8000_e:",
    "            rec['gen_kind'] = 'ba8000-error'",
    "            rec['ba8000_error'] = repr(_ba8000_e)[:200]",
]

BLOCK_LINES = MANAGED_BLOCK.rstrip('\n').split('\n')


# ================================================================ utilities
def die(msg, code=2):
    sys.stderr.write("ERROR: %s\n" % msg)
    raise SystemExit(code)


def read_text(path):
    """读文本并**去掉 BOM**（Windows 编辑器常加，Python compile 会报 U+FEFF）。"""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    return raw.decode("utf-8")


def has_bom(path):
    try:
        with open(path, "rb") as fh:
            return fh.read(3) == b"\xef\xbb\xbf"
    except OSError:
        return False


def write_text_atomic(path, text, bom=False):
    tmp = path + ".tmp8000"
    data = text.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    with open(tmp, "wb") as fh:
        fh.write(data)
    if os.path.exists(path):
        try:
            shutil.copymode(path, tmp)
        except Exception:
            pass
    os.replace(tmp, path)


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_path(target, ts):
    """Never collide: two applies in the same second must not clobber the original."""
    bak = target + ".bak." + ts
    n = 1
    while os.path.exists(bak):
        bak = target + ".bak." + ts + "_%d" % n
        n += 1
    return bak


def list_backups(target):
    d = os.path.dirname(os.path.abspath(target)) or "."
    base = os.path.basename(target) + ".bak."
    out = []
    try:
        for n in os.listdir(d):
            if n.startswith(base):
                out.append(os.path.join(d, n))
    except OSError:
        pass
    out.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return out


def eol_cr(text):
    crlf = text.count("\r\n")
    return "\r" if crlf > (text.count("\n") - crlf) else ""


# ================================================================ 文本手术
def find_block(lines):
    bi = ei = None
    for i, raw in enumerate(lines):
        s = raw.rstrip("\r")
        if s == BEGIN and bi is None:
            bi = i
        elif s == END and bi is not None and ei is None:
            ei = i
            break
    if bi is not None and ei is None:
        die("managed block 有 BEGIN 没有 END —— 拒绝改动这个文件")
    return bi, ei


def find_anchor(lines):
    """模块级插入点：SESSION = Session() 之后；退化到最后一个 import。"""
    for i, raw in enumerate(lines):
        if raw.rstrip("\r") == "SESSION = Session()":
            return i
    last = None
    for i, raw in enumerate(lines):
        s = raw.rstrip("\r")
        if s.startswith("import ") or s.startswith("from "):
            last = i
    return last if last is not None else 0


def find_branch(lines, proto=8000):
    """-> (start, end, indent) of the whole `if num == %d:` branch, or None."""
    pat = re.compile(r"^(\s*)if\s+num\s*==\s*%d\s*:\s*$" % proto)
    for i, raw in enumerate(lines):
        m = pat.match(raw.rstrip("\r"))
        if not m:
            continue
        indent = m.group(1)
        j = i + 1
        while j < len(lines):
            cand = lines[j].rstrip("\r")
            if cand.strip() == "":
                j += 1
                continue
            cur = len(cand) - len(cand.lstrip())
            if cur <= len(indent):
                break
            j += 1
        end = j
        while end > i + 1 and lines[end - 1].strip() == "":
            end -= 1
        return i, end, indent
    return None


def find_insert_point(lines, proto=8000):
    """没找到 `if num == 8000:` 时，找一个安全的位置新建分支。

    候选锚点（按顺序）：
      `if num == 24000:` 之后 / 任何 `if num == <int>:` 分支之后 / `else:` 之前
    找不到就报错，绝不瞎猜。
    """
    br = find_branch(lines, 24000)
    if br:
        return br[1], br[2]
    anynum = None
    for i, raw in enumerate(lines):
        m = re.match(r"^(\s*)if\s+num\s*==\s*\d+\s*:\s*$", raw.rstrip("\r"))
        if m:
            anynum = (i, m.group(1))
    if anynum:
        b = find_branch(lines, int(re.search(r"num\s*==\s*(\d+)",
                                            lines[anynum[0]].rstrip("\r")).group(1)))
        if b:
            return b[1], b[2]
    for i, raw in enumerate(lines):
        m = re.match(r"^(\s*)else\s*:\s*$", raw.rstrip("\r"))
        if m and len(m.group(1)) <= 8:
            return i, m.group(1)
    die("找不到 `if num == <proto>:` 分支，也找不到可用的插入锚点 —— "
        "请用 --branch-anchor 指定行号，或先人工确认 bridge 的分发结构")


def apply_edits(text, catalog_path, switch_path, defaults):
    # 注意：这里嵌进去的是 **Python 源码**，所以默认字典必须用 repr()（True/False），
    # 不能用 json.dumps()（会写出 JSON 的 true/false → NameError）。
    block = (MANAGED_BLOCK
             .replace("__BA8000_CATALOG__", repr(catalog_path))
             .replace("__BA8000_SWITCH__", repr(switch_path))
             .replace("__BA8000_DEFAULT_SWITCH__", repr(dict(defaults))))
    lines = text.split("\n")
    cr = eol_cr(text)
    blk = [l + cr for l in block.rstrip("\n").split("\n")]
    bi, ei = find_block(lines)
    changed_block = False
    if bi is not None:
        if lines[bi:ei + 1] != blk:
            lines[bi:ei + 1] = blk
            changed_block = True
    else:
        anchor = find_anchor(lines)
        tail = [cr] if (anchor + 1 >= len(lines) or lines[anchor + 1].strip() != "") else []
        lines[anchor + 1:anchor + 1] = [cr] + blk + tail
        changed_block = True
    text2 = "\n".join(lines)

    # ---- 分支
    lines2 = text2.split("\n")
    br = find_branch(lines2, 8000)
    how = "already"
    if br:
        start, end, indent = br
        if lines2[start:end] != [indent + b + cr for b in BRANCH_NEW]:
            lines2[start:end] = [indent + b + cr for b in BRANCH_NEW]
            how = "replaced"
    else:
        at, indent = find_insert_point(lines2, 8000)
        lines2[at:at] = [indent + b + cr for b in BRANCH_NEW] + [cr]
        how = "inserted"
    return "\n".join(lines2), changed_block, how


# ================================================================ 数据文件
def build_catalog_text():
    """优先用 gen8000.py 现算（同目录），否则用现成的 8000_catalog.json。"""
    try:
        sys.path.insert(0, HERE)
        import gen8000                                        # noqa: E402
        cat = gen8000.Catalog()
        rows = [[m.uid, m.category,
                 m.event_id if m.event_id is not None else 0,
                 m.f15 if m.f15 is not None else 0,
                 m.f16 if m.f16 is not None else 0]
                for m in sorted(cat._by_uid.values(), key=lambda x: x.uid)]
        cat.close()
        doc = {"_meta": {"protocol": 8000, "protocol_name": "Mission_List",
                         "count": len(rows),
                         "format": "[uid, category, event_content_id, f15, f16]",
                         "generated_by": "gen8000.Catalog",
                         "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")},
               "rows": rows}
        return json.dumps(doc, ensure_ascii=False, separators=(",", ":")), len(rows), "gen8000"
    except Exception as e:                                    # noqa: BLE001
        if os.path.exists(LOCAL_CATALOG):
            text = read_text(LOCAL_CATALOG)
            n = len(json.loads(text).get("rows") or [])
            return text, n, "file(%s, gen8000 不可用: %r)" % (LOCAL_CATALOG, e)
        die("既算不出目录（gen8000 不可用: %r），也找不到 %s" % (e, LOCAL_CATALOG))


def deploy_data_file(path, text, ts, dry):
    """写入数据文件；内容一致就 no-op，不同才备份。"""
    if os.path.exists(path):
        cur = open(path, "rb").read()
        if cur == text.encode("utf-8"):
            return "unchanged", None
        bak = path + ".bak." + ts
        if not dry:
            shutil.copy2(path, bak)
    else:
        bak = None
    if not dry:
        d = os.path.dirname(os.path.abspath(path))
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with open(path, "wb") as fh:
            fh.write(text.encode("utf-8"))
    return "written", bak


def write_switch(path, ts, dry, **over):
    cur = {}
    if os.path.exists(path):
        try:
            cur = json.loads(read_text(path))
        except Exception:
            cur = {}
    cfg = dict(DEFAULT_SWITCH)
    cfg.update(cur if isinstance(cur, dict) else {})
    cfg.update(over)
    text = json.dumps(cfg, ensure_ascii=False, indent=1) + "\n"
    state, bak = deploy_data_file(path, text, ts, dry)
    return cfg, state, bak


# ================================================================ 渲染探针
def probe_render(text, frag=None, cfg_over=None):
    """把 managed block 单独 exec 出来，用假请求渲染一次。

    不 import bridge（它依赖服务器环境），只取 block 里的函数。
    cfg_over 非空时**屏蔽真实开关文件**，让探针结果可复现（verify 要确定性）。
    """
    lines = text.split("\n")
    bi, ei = find_block(lines)
    if bi is None:
        die("block 不在，无法 verify")
    block = "\n".join(lines[bi + 1:ei])

    # cn_wire 在服务器上与 bridge 同目录；本地演练时用替身，保证 verify 不联网
    ns = {"__name__": "_ba8000_probe"}
    try:
        import cn_wire                                          # noqa: F401
        ns["cn_wire"] = cn_wire
    except Exception:
        class _StubWire(object):
            @staticmethod
            def wrap_response(proto_name, obj, rid):
                plain = json.dumps({"protocol": proto_name, "packet":
                                    json.dumps(obj, ensure_ascii=False,
                                               separators=(",", ":")),
                                    "requestid": rid},
                                   ensure_ascii=False, separators=(",", ":"))
                return "WIRE:" + hashlib.sha256(plain.encode()).hexdigest(), plain, rid
        ns["cn_wire"] = _StubWire

    exec(compile(block, "<ba8000-block>", "exec"), ns)          # noqa: S102
    if cfg_over is not None:
        # 指向一个必然不存在的路径 → _ba8000_switch() 落到默认字典
        ns["_BA8000_SWITCH_FILE"] = os.path.join(
            HERE, "_ba8000_probe_nonexistent_switch.json")
        ns["_BA8000_DEFAULT_SWITCH"].update(cfg_over)
        ns["_BA8000_SW_CFG"]["key"] = None
        ns["_BA8000_SW_CFG"]["cfg"] = None
    rec = {}
    obj = ns["_ba8000_build"](frag or {}, rec)
    return obj, rec, ns


# ================================================================ 模式
def cmd_status(a):
    out = []
    tgt = a.target
    out.append("target   : %s%s" % (tgt, "" if os.path.exists(tgt) else "   (不存在)"))
    if os.path.exists(tgt):
        text = read_text(tgt)
        lines = text.split("\n")
        bi, ei = find_block(lines)
        out.append("managed block: %s" % ("在 (行 %d..%d)" % (bi + 1, ei + 1) if bi else "不在"))
        br = find_branch(lines, 8000)
        out.append("分支 if num==8000: %s" % (
            "在 (行 %d..%d)" % (br[0] + 1, br[1]) if br else "不在"))
        m = re.search(r"_BA8000_CATALOG_FILE\s*=\s*(.+)$", text, re.M)
        if m:
            out.append("block 里的 catalog 路径: %s" % m.group(1).strip())
    out.append("catalog  : %s" % a.catalog)
    if os.path.exists(a.catalog):
        try:
            doc = json.loads(read_text(a.catalog))
            out.append("           %d 条, %d 字节" % (
                len(doc.get("rows") or []), os.path.getsize(a.catalog)))
        except Exception as e:
            out.append("           解析失败: %r" % (e,))
    else:
        out.append("           不存在")
    out.append("switch   : %s" % a.switch)
    if os.path.exists(a.switch):
        try:
            out.append("           %s" % json.dumps(json.loads(read_text(a.switch)),
                                                     ensure_ascii=False))
        except Exception as e:
            out.append("           解析失败: %r" % (e,))
    else:
        out.append("           不存在（运行时用默认值）")
    baks = list_backups(tgt) if os.path.exists(tgt) else []
    out.append("备份     : %d 个%s" % (len(baks), ("，最新 " + os.path.basename(baks[0]))
                                       if baks else ""))
    print("\n".join(out))
    return 0


def cmd_apply(a):
    tgt = a.target
    if not os.path.exists(tgt):
        die("目标文件不存在: %s\n（本地演练请用 --target 指向一个测试副本；"
            "本脚本不会去连服务器）" % tgt)
    text = read_text(tgt)
    bom = has_bom(tgt)
    before = sha256(text)

    catalog_text, nrows, src = build_catalog_text()
    defaults = dict(DEFAULT_SWITCH)
    if os.path.exists(a.switch):
        try:
            defaults.update(json.loads(read_text(a.switch)))
        except Exception:
            pass

    new_text, changed_block, how = apply_edits(text, a.catalog, a.switch, defaults)

    # ---- 语法检查（绝不写半个坏文件）
    try:
        compile(new_text, tgt, "exec")
    except SyntaxError as e:
        die("打完补丁语法检查失败，已放弃写入: %s (line %s)" % (e, e.lineno))

    if new_text == text:
        print("目标已是最新，逐字节 no-op（不备份、不写）")
        wrote_target = False
    else:
        d = difflib.unified_diff(text.split("\n"), new_text.split("\n"),
                                 fromfile=tgt + " (before)", tofile=tgt + " (after)",
                                 lineterm="", n=2)
        diff = "\n".join(d)
        if a.dry_run:
            print("---- dry-run：将写入 %s ----" % tgt)
            print(diff[:8000] + ("\n... (diff 截断)" if len(diff) > 8000 else ""))
        else:
            bak = backup_path(tgt, stamp())
            shutil.copy2(tgt, bak)
            write_text_atomic(tgt, new_text, bom)
            print("已修改 %s" % tgt)
            print("  备份      : %s" % bak)
            print("  sha256    : %s → %s" % (before[:16], sha256(new_text)[:16]))
        wrote_target = True

    print("  块         : %s" % ("更新" if changed_block else "已是目标内容"))
    print("  分支       : %s" % how)
    print("  目录       : %d 条 (%s)" % (nrows, src))

    ts = stamp()
    state, bak = deploy_data_file(a.catalog, catalog_text, ts, a.dry_run)
    print("  部署目录   : %s → %s%s" % (
        a.catalog, state, ("（备份 %s）" % bak) if bak else ""))

    cfg, sstate, sbak = write_switch(a.switch, ts, a.dry_run, **{
        k: v for k, v in (a.set_switch or {}).items()})
    print("  部署开关   : %s → %s%s" % (
        a.switch, sstate, ("（备份 %s）" % sbak) if sbak else ""))

    if a.dry_run:
        print("\n(dry-run：以上都没有真正写入)")
        return 0
    if not wrote_target and state == "unchanged" and sstate == "unchanged":
        print("\n一切已就绪，无改动。")
    else:
        print("\n完成。建议立刻跑 --verify，然后重启 bridge 让模块级 block 生效。")
        print("  软关（不还原源码）: %s --target %s --disable" % (
            os.path.basename(__file__), tgt))
    return 0


def cmd_verify(a):
    tgt = a.target
    fails = []
    if not os.path.exists(tgt):
        die("目标文件不存在: %s" % tgt)
    text = read_text(tgt)
    lines = text.split("\n")

    # 1 语法
    try:
        compile(text, tgt, "exec")
        print("[1/6] 语法          : OK")
    except SyntaxError as e:
        fails.append("语法错误: %s (line %s)" % (e, e.lineno))
        print("[1/6] 语法          : FAIL %s" % e)

    # 2 标记配对
    bi, ei = find_block(lines)
    if bi is not None:
        print("[2/6] managed block : 在 行 %d..%d（%d 行）" % (bi + 1, ei + 1, ei - bi + 1))
    else:
        fails.append("managed block 不在")
        print("[2/6] managed block : 不在")

    # 3 分支委托
    br = find_branch(lines, 8000)
    if br:
        body = "\n".join(lines[br[0]:br[1]])
        ok = "_ba8000_build" in body and "_ba8000_send" in body
        print("[3/6] 分支          : 行 %d..%d 委托=%s" % (
            br[0] + 1, br[1], "是" if ok else "否"))
        if not ok:
            fails.append("分支体没有委托到 _ba8000_build/_ba8000_send")
    else:
        fails.append("`if num == 8000:` 分支不在")
        print("[3/6] 分支          : 不在")

    # 4 数据文件
    print("[4/6] 目录          : %s" % a.catalog)
    nrows = 0
    if os.path.exists(a.catalog):
        try:
            doc = json.loads(read_text(a.catalog))
            nrows = len(doc.get("rows") or [])
            fmt_ok = nrows > 7000 and all(isinstance(r, list) and len(r) >= 5
                                         for r in (doc.get("rows") or [])[:50])
            print("                    : %d 条, 格式=%s" % (
                nrows, "OK" if fmt_ok else "[uid,cat,ev,f15,f16] 不符"))
            if not fmt_ok:
                fails.append("目录条数或格式不对（期望 >7000 且 5 元组）")
        except Exception as e:
            fails.append("目录解析失败: %r" % (e,))
    else:
        fails.append("目录文件不存在")
    print("[5/6] 开关          : %s" % a.switch)
    if os.path.exists(a.switch):
        try:
            cfg = json.loads(read_text(a.switch))
            print("                    : %s" % json.dumps(cfg, ensure_ascii=False))
            if "enabled" not in cfg:
                fails.append("开关文件缺 enabled 键")
        except Exception as e:
            fails.append("开关解析失败: %r" % (e,))
    else:
        print("                    : 不存在（运行时用 block 内默认值）")

    # 6 渲染探针：三个变体（显式注入开关，结果与已部署开关无关）
    print("[6/6] 渲染          :")
    probes = [
        ("full/seed", {}, {"enabled": True, "profile": "seed"}),
        ("full/empty", {}, {"enabled": True, "profile": "empty"}),
        ("event 849", {"EventContentId": 849}, {"enabled": True, "profile": "seed"}),
        ("event 10838", {"EventContentId": 10838}, {"enabled": True, "profile": "seed"}),
    ]
    base = {"SessionKey": {"AccountServerId": a.account_id,
                           "MxToken": "V" * 64},
            "AccountId": a.account_id}
    rendered = []
    for label, extra, cfg in probes:
        frag = dict(base)
        frag.update(extra)
        try:
            obj, rec, _ns = probe_render(text, frag, cfg)
        except Exception as e:
            fails.append("%s 渲染失败: %r" % (label, e))
            print("                    : %-12s FAIL %r" % (label, e))
            continue
        keys = list(obj.keys())
        okkey = keys == OFFICIAL_TOP_KEYS
        if not okkey:
            fails.append("%s 顶层键序不对: %s" % (label, keys))
        if obj.get("HistoryDBs", "MISSING") is not None:
            fails.append("%s HistoryDBs 不是 null" % label)
        n = len(obj.get("ProgressDBs") or [])
        print("                    : %-12s 键序=%s 条数=%-5d variant=%s" % (
            label, "OK" if okkey else "FAIL", n, rec.get("ba8000_variant")))
        rendered.append((label, obj))

    # 用 spec_check 复核（本地有 spec 才算）
    spec_dir = os.path.join(ROOT, "work", "ba", "proto")
    if not os.path.isdir(spec_dir):
        print("                    : spec_check 跳过（找不到 %s）" % spec_dir)
    if os.path.isdir(spec_dir):
        sys.dont_write_bytecode = True
        sys.path.insert(0, spec_dir)
        try:
            import spec_check                                 # noqa: E402
            spec = json.load(open(os.path.join(spec_dir, "official_spec.json"),
                                  encoding="utf-8"))
            for label, obj in rendered:
                rep, _e = spec_check.check_one(8000, obj, spec, "<probe:%s>" % label)
                kinds = {}
                for k, _p, _d in rep.warns:
                    kinds[k] = kinds.get(k, 0) + 1
                print("                    : %-12s spec_check=%s FAIL=%d WARN=%d %s" % (
                    label, "PASS" if not rep.fails else "FAIL",
                    len(rep.fails), len(rep.warns),
                    ("(" + ", ".join("%s=%d" % kv for kv in sorted(kinds.items())) + ")"
                     if kinds else "")))
                if rep.fails:
                    fails.append("spec_check %s FAIL %d" % (label, len(rep.fails)))
        except Exception as e:
            print("                    : spec_check 跳过（%r）" % (e,))

    print("")
    if fails:
        print("verify: FAIL %d 项" % len(fails))
        for f in fails:
            print("  - %s" % f)
        return 1
    print("verify: PASS")
    return 0


def cmd_rollback(a):
    tgt = a.target
    if not os.path.exists(tgt):
        die("目标文件不存在: %s" % tgt)
    baks = list_backups(tgt)
    if not baks:
        die("没有找到 %s.bak.<TS> 备份，无法回滚" % tgt)

    if a.rollback_to:
        if not os.path.exists(a.rollback_to):
            die("--rollback-to 指定的文件不存在: %s" % a.rollback_to)
        src = a.rollback_to
        why = "--rollback-to 显式指定"
    else:
        # 默认：还原到**不含 managed block 的真原件**（而不是"上一版补丁"）。
        # 目的就是"撤掉 8000"，所以往回找第一个干净备份；找不到才退回最新备份。
        src = None
        for p in baks:                       # 新 → 旧
            try:
                if BEGIN not in read_text(p):
                    src = p
                    break
            except Exception:
                continue
        if src is None:
            src = baks[0]
            why = "没有找到干净备份，退回最新备份 %s" % os.path.basename(src)
        else:
            why = "找到不含 managed block 的原件 %s" % os.path.basename(src)

    text = read_text(tgt)
    old = read_text(src)
    bom = has_bom(tgt)
    print("回滚 %s" % tgt)
    print("  依据        : %s" % why)
    print("  当前 sha256 : %s" % sha256(text)[:16])
    print("  还原自      : %s" % src)
    print("  还原后 sha  : %s" % sha256(old)[:16])
    print("  还原后仍有 block: %s" % ("是（这不是干净原件，注意）"
                                      if BEGIN in old else "否（干净）"))
    if text == old:
        print("  内容相同，无需改动")
        return 0
    if a.dry_run:
        d = difflib.unified_diff(text.split("\n"), old.split("\n"),
                                 fromfile="current", tofile=os.path.basename(src),
                                 lineterm="", n=2)
        print("---- dry-run：将还原创回 %s ----" % tgt)
        print("\n".join(d)[:8000])
        return 0
    keep = backup_path(tgt, stamp())
    shutil.copy2(tgt, keep)
    write_text_atomic(tgt, old, bom)
    print("  当前版本另存: %s" % keep)
    # 顺手把开关置 false，避免回滚后还有别的东西触发 8000
    if a.disable_after_rollback and os.path.exists(a.switch):
        cfg, state, _b = write_switch(a.switch, stamp(), False, enabled=False)
        print("  开关改为 enabled=false → %s (%s)" % (a.switch, state))
    print("完成。记得重启 bridge。")
    return 0


def cmd_toggle(a, enabled):
    cfg, state, bak = write_switch(a.switch, stamp(), a.dry_run, enabled=enabled)
    print("开关 %s → %s (%s)" % (a.switch, state, json.dumps(cfg, ensure_ascii=False)))
    if bak:
        print("  备份: %s" % bak)
    if a.dry_run:
        print("  (dry-run，未写入)")
    return 0


# ================================================================ main
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Mission_List(8000) bridge 补丁（幂等，带独立开关文件）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("--target", default=DEFAULT_TARGET,
                    help="要打补丁的 bridge（默认服务器路径 %s；本地演练请覆盖）"
                         % DEFAULT_TARGET)
    ap.add_argument("--catalog", default=None,
                    help="任务目录文件（默认与 bridge 同目录的 %s）" % DEFAULT_CATALOG_NAME)
    ap.add_argument("--switch", default=None,
                    help="独立开关文件（默认与 bridge 同目录的 %s）" % DEFAULT_SWITCH_NAME)
    ap.add_argument("--account-id", type=int, default=10015354380,
                    help="verify 渲染探针用的账号")
    ap.add_argument("--apply", action="store_true", help="打补丁（默认动作）")
    ap.add_argument("--dry-run", action="store_true", help="只打印 diff，不写任何文件")
    ap.add_argument("--verify", action="store_true", help="校验（语法/标记/分支/数据/渲染/spec）")
    ap.add_argument("--rollback", action="store_true", help="从备份还原（默认还原到不含 block 的真原件）")
    ap.add_argument("--rollback-to", default=None, metavar="PATH",
                    help="回滚到指定的备份文件（覆盖默认的自动挑选）")
    ap.add_argument("--status", action="store_true", help="打印当前状态")
    ap.add_argument("--enable", action="store_true", help="只把开关置 true")
    ap.add_argument("--disable", action="store_true", help="只把开关置 false")
    ap.add_argument("--set-switch", action="append", default=None, metavar="K=V",
                    help="apply 时顺带改开关项，可多次，如 --set-switch profile=empty")
    ap.add_argument("--disable-after-rollback", action="store_true",
                    help="rollback 后把开关置 false")
    a = ap.parse_args(argv)

    # 数据文件默认跟随 target 所在目录
    tdir = os.path.dirname(os.path.abspath(a.target)) or "."
    if a.catalog is None:
        a.catalog = os.path.join(tdir, DEFAULT_CATALOG_NAME)
    if a.switch is None:
        a.switch = os.path.join(tdir, DEFAULT_SWITCH_NAME)

    if a.set_switch:
        d = {}
        for s in a.set_switch:
            if "=" not in s:
                die("--set-switch 需要 K=V，收到 %r" % s)
            k, v = s.split("=", 1)
            k = k.strip()
            v = v.strip()
            try:
                d[k] = json.loads(v)
            except Exception:
                d[k] = v
        a.set_switch = d
    else:
        a.set_switch = {}

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if a.status:
        return cmd_status(a)
    if a.verify:
        return cmd_verify(a)
    if a.rollback:
        return cmd_rollback(a)
    if a.enable:
        return cmd_toggle(a, True)
    if a.disable:
        return cmd_toggle(a, False)
    return cmd_apply(a)


if __name__ == "__main__":
    sys.exit(main())
