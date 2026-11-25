"""我们的国服 SDK 服务（卡密版）。

- /common/config      -> 返回抓下来的真实配置（检测地址改指我们）
- /user/login         -> OpenID 字段就是卡密，校验通过即签发 token
- /user/quick-login   -> 已绑定设备直接放行，否则要求输卡密
- 其他                 -> 记录 + 通用成功
卡密库：/root/bapatch/cards.json
"""
import json, os, time, hashlib

# [PATCH-PY-20261118v2]
MAX_SDK_BODY = 4194304
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = '/www/wwwroot/ba_sdk/sdk.log'
CARDS = "/www/wwwroot/ba_sdk/cards.json"
CFG = '/www/wwwroot/ba_sdk/resp/common_config.json'
TEMPLATE = '/www/wwwroot/ba_sdk/resp/user_quick-login.json'


def w(s):
    with open(LOG, 'a') as f:
        f.write(s + '\n')


import threading, tempfile
CARDS_LOCK = threading.RLock()


def load_cards():
    with CARDS_LOCK:
        if not os.path.exists(CARDS):
            return {"cards": {}}
        try:
            with open(CARDS, encoding="utf-8") as f:
                d = json.load(f)
        except Exception as e:
            bak = CARDS + ".corrupt.%d" % int(time.time())
            try:
                os.replace(CARDS, bak)
            except Exception:
                pass
            raise RuntimeError("cards.json unreadable, backed up to %s: %r" % (bak, e))
        if not isinstance(d, dict) or "cards" not in d:
            bak = CARDS + ".corrupt.%d" % int(time.time())
            try:
                os.replace(CARDS, bak)
            except Exception:
                pass
            raise RuntimeError("cards.json shape invalid, backed up to %s" % bak)
        return d


def save_cards(d):
    with CARDS_LOCK:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(CARDS) or ".", prefix=".cards.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, CARDS)
        finally:
            if os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except Exception:
                    pass


def _mask(v):
    s = str(v)
    return s if len(s) <= 8 else "%s****%s(len=%d)" % (s[:4], s[-4:], len(s))


def device_of(handler):
    raw = handler.headers.get('Authorization') or ''
    try:
        head = json.loads(raw).get('Head', {})
        return head.get('DeviceID', '') or ''
    except Exception:
        return ''


# >>> BAPATCH-DEVBAN v1 >>>
# 设备封禁黑名单：运营在面板里按设备封人（设备号 = Authorization 头里的 Head.DeviceID）。
# 安全默认：文件不存在 / 读失败 / 编码异常 / 设备号为空 一律放行，绝不抛。
# 格式：每行一个设备号（大小写不敏感，strip 后比较），空行与 # 开头的行忽略。
DEVICE_BAN_FILE = os.environ.get('BA_DEVICE_BAN_FILE') or '/www/wwwroot/ba_sdk/device_ban.txt'
DEVICE_BAN_PATHS = ('/user/login', '/user/quick-login', '/user/detail')
DEVICE_BAN_CODE = 400101
DEVICE_BAN_MSG = '设备已被限制'
DEVICE_BAN_LOCK = threading.Lock()
_DEVICE_BAN_CACHE = {'key': None, 'banned': frozenset()}


def _device_ban_load():
    """读黑名单文件 -> frozenset(小写设备号)。任何异常返回空集合。"""
    try:
        with open(DEVICE_BAN_FILE, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.read().splitlines()
    except Exception:
        return frozenset()
    out = set()
    for line in lines:
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        out.add(s.lower())
    return frozenset(out)


def device_banned(dev):
    """True = 该设备已被封禁。进程内按 (mtime_ns, size) 缓存，文件一变自动失效。绝不抛。"""
    try:
        d = str(dev or '').strip().lower()
        if not d:
            return False
        try:
            st = os.stat(DEVICE_BAN_FILE)
            stamp = (st.st_mtime_ns, st.st_size)
        except Exception:
            return False
        with DEVICE_BAN_LOCK:
            if _DEVICE_BAN_CACHE['key'] == stamp:
                return d in _DEVICE_BAN_CACHE['banned']
        banned = _device_ban_load()
        with DEVICE_BAN_LOCK:
            _DEVICE_BAN_CACHE['key'] = stamp
            _DEVICE_BAN_CACHE['banned'] = banned
        return d in banned
    except Exception:
        return False


def device_ban_resp(dev, path):
    """命中返回响应 dict（调用方立刻 _send 并 return），未命中返回 None。"""
    if not device_banned(dev):
        return None
    try:
        w('DEVICE BANNED %s path=%s' % (_mask(dev), path))
    except Exception:
        pass
    return {'Code': DEVICE_BAN_CODE, 'Msg': DEVICE_BAN_MSG, 'Data': {}}
# <<< BAPATCH-DEVBAN v1 <<<


# >>> BAPATCH-BANEXP v1 >>>
# 限时 / 永久封禁（三个维度共用桥接库里的 bans 表；**到期判定在读取侧**，不靠任何定时任务）。
#   账号 -> bans(kind='account', target=<publisherId>)，publisherId = 登录时由卡密算出来的那个号
#   卡密 -> bans(kind='card',    target=<卡密>)
#   设备 -> bans(kind='device',  target=<设备号>)
# 命中就回 {'Code':400101,'Msg':<文案>,'Data':{}}，文案由 ban_message.py 统一生成：
#   永久 -> 封禁，请联系客服
#   限时 -> 封号时间 2026-11-18 20:00 至 2026-11-20 20:00，请联系客服
#
# [PATCH-PY-20261118-gatefix] 拦截维度（默认值）：
#   设备 -> **拦**（设备没有游戏层可拦的地方）
#   卡密 -> 付费卡**不拦**（交给游戏层；公益卡仍然拦，它映射不出 publisher）
#   账号 -> **不拦**（交给游戏层，客户端才会弹官方 AccountBanErrorPacket）
#   两把开关：/www/wwwroot/bapatch/cn_sdk_ban_card.txt、cn_sdk_ban_account.txt，
#   写 1 即恢复旧行为（每请求现读，不用重启）。
#
# 安全默认（缺一不可地"放行"）：
#   · ban_message.py 不在 -> BANEXP_ON=False，整段判定直接跳过（行为 == 基线 DEVBAN 版）
#   · 库不存在 / 没表 / 读失败 / 任何异常 -> 当作"没封禁"放行，绝不抛
#   · 这里只**读** cards.json（不走 load_cards()），不备份、不迁移、不写盘，命中与否都不改任何状态
BANEXP_DB = os.environ.get('BA_BANS_DB') or os.environ.get('BA_ACCT_DB') or \
    '/www/wwwroot/bapatch/data/accounts.db'
BANEXP_CODE = DEVICE_BAN_CODE
BANEXP_SQLITE_TIMEOUT = 1.0

try:
    from ban_message import ban_message_for_row as _banexp_text_of_row
    from ban_message import is_active as _banexp_is_active
    BANEXP_ON = True
except Exception:
    _banexp_text_of_row = None
    _banexp_is_active = None
    BANEXP_ON = False

try:
    import sqlite3 as _banexp_sqlite3
except Exception:
    _banexp_sqlite3 = None


def _banexp_ro_uri(path):
    """绝对路径 -> SQLite 只读 URI。Windows 的盘符路径要变成 file:/C:/... 才认。"""
    import urllib.parse as _up
    p = os.path.abspath(str(path)).replace('\\', '/')
    if not p.startswith('/'):
        p = '/' + p
    return 'file:' + _up.quote(p, safe='/:') + '?mode=ro'


def _banexp_connect():
    """只读打开 accounts.db（mode=ro：连 ATTACH 写都做不到）。"""
    if _banexp_sqlite3 is None:
        raise RuntimeError('no sqlite3')
    return _banexp_sqlite3.connect(_banexp_ro_uri(BANEXP_DB), uri=True,
                                  timeout=BANEXP_SQLITE_TIMEOUT)


def banexp_row(kind, target):
    """读 bans 表的一行 -> dict | None。任何异常（没库/没表/被锁/字段不对）都返回 None。"""
    try:
        t = str(target or '').strip()
        k = str(kind or '').strip()
        if not t or k not in ('account', 'card', 'device'):
            return None
        row = None
        conn = _banexp_connect()
        try:
            cur = conn.execute(
                'SELECT kind, target, until_epoch, reason, created_at FROM bans'
                ' WHERE kind = ? AND target = ? LIMIT 1', (k, t))
            row = cur.fetchone()
            if row is None and k == 'device':
                # 设备号按大小写不敏感兜一次（黑名单文件本来就是这么比的；表很小，扫一遍无所谓）
                cur = conn.execute(
                    'SELECT kind, target, until_epoch, reason, created_at FROM bans'
                    ' WHERE kind = ? AND LOWER(target) = LOWER(?) LIMIT 1', (k, t))
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


def banexp_state(kind, target):
    """-> ('none'|'active'|'expired', row|None)。读失败一律 'none'（放行）。"""
    row = banexp_row(kind, target)
    if row is None:
        return 'none', None
    try:
        if _banexp_is_active(row.get('until_epoch')):
            return 'active', row
    except Exception:
        return 'none', None
    return 'expired', row


def banexp_resp(kind, row, label):
    """命中 -> 响应 dict（带封禁文案）。文案算不出来就退回旧文案，绝不炸。"""
    msg = ''
    try:
        msg = _banexp_text_of_row(row)
    except Exception:
        msg = ''
    if not isinstance(msg, str) or msg.strip() == '':
        msg = DEVICE_BAN_MSG
    try:
        w('BANEXP %s %s until=%s path=%s' % (
            str(kind).upper(), _mask(label), row.get('until_epoch'), row.get('reason')))
    except Exception:
        pass
    return {'Code': BANEXP_CODE, 'Msg': msg, 'Data': {}}


def _banexp_cards_snapshot():
    """纯只读地读一张 cards.json 快照（不调用 load_cards：不备份/不迁移/不写盘）。"""
    try:
        with open(CARDS, 'r', encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get('cards'), dict):
            return d
    except Exception:
        pass
    return {'cards': {}}


def banexp_card_of(path, body, dev):
    """这次请求在用的卡密 -> (card_key, rec)。取不到返回 (None, None)。"""
    try:
        snap = _banexp_cards_snapshot()
        cards = snap.get('cards') or {}
        if path == '/user/login':
            try:
                j = json.loads(body or b'{}')
            except Exception:
                return None, None
            key = str((j or {}).get('OpenID') or '').strip()
            if not key:
                return None, None
            rec = cards.get(key)
            return key, (rec if isinstance(rec, dict) else None)
        key, rec = pick_card_for_device(snap, dev)
        if not key:
            return None, None
        return str(key), (rec if isinstance(rec, dict) else None)
    except Exception:
        return None, None


# [PATCH-PY-20261118-sdkaccount] SDK 层是否继续拦「账号」维度：默认「不拦」。
#
# 背景：账号封禁在 SDK 层（8080）拦下后，客户端只显示「未知错误，请联系客服」
# （客户端不渲染 /user/login 返回的 Msg），玩家根本到不了游戏层，于是桥（9097）
# 里那套官方封禁弹窗（Protocol.Error + ErrorCode=1025 + BanReason）永远看不到。
# 所以账号维度交给游戏层拦；卡密 / 设备两个维度仍然在这里拦（没有更合适的拦截点）。
#
# 开关优先级：
#   ① 环境变量 CN_SDK_BAN_ACCOUNT 非空 -> 只按它的值判定；
#   ② 文件 BANEXP_ACCOUNT_SWITCH_FILE 的内容。
# 真值 1/on/true/yes（大小写不敏感、去首尾空白）=> True：SDK 恢复拦账号（旧行为）。
# 文件不存在 / 空 / 其它值 / 读失败 / 解析失败 / 任何异常 => False：SDK 不拦账号（新行为）。
# 每请求现读文件，所以线上写一个 1 就秒回退旧行为（不用重启、不用重新部署）；
# 删掉文件即回到新行为。
BANEXP_ACCOUNT_SWITCH_FILE = (os.environ.get('CN_SDK_BAN_ACCOUNT_FILE')
                              or '/www/wwwroot/bapatch/cn_sdk_ban_account.txt')
BANEXP_ACCOUNT_YES = ('1', 'on', 'true', 'yes')


def _banexp_account_flag(v):
    """1/on/true/yes（大小写不敏感、去首尾空白）=> True；其它一切 => False。绝不抛。"""
    try:
        return str(v if v is not None else '').strip().lower() in BANEXP_ACCOUNT_YES
    except Exception:
        return False


def banexp_sdk_bans_account():
    """True = SDK 层也拦账号（旧行为）；False = 不拦账号、交给游戏层（默认）。绝不抛。"""
    try:
        env = os.environ.get('CN_SDK_BAN_ACCOUNT')
        if env is not None and str(env).strip() != '':
            return _banexp_account_flag(env)
        try:
            with open(BANEXP_ACCOUNT_SWITCH_FILE, 'r', encoding='utf-8', errors='replace') as f:
                return _banexp_account_flag(f.read())
        except Exception:
            return False
    except Exception:
        return False


# [PATCH-PY-20261118-gatefix] SDK 层是否继续拦「卡密」维度：默认「不拦」（付费卡）。
#
# 背景：卡密封禁也已经迁到游戏层 —— 面板禁用一张**付费卡**时，会按
# publisher = md5(卡密) 把它映射成一条 bans(kind='account') 行（inc/bans.php 的
# bancard_account_apply / inc/sync.php 的对账），桥（9097）读到就回官方封禁包
# （Protocol=-1, ErrorCode=1025, BanReason）。SDK 这一层要是先把人拦下，客户端只显示
# 「未知错误/卡密不正确」，玩家到不了游戏层，官方封禁文案永远看不到。所以卡密维度默认放行。
#
# **公益卡（kind='free'）例外，永远在 SDK 拦**：它的账号按设备算
# （publisher = md5('free:'+设备)），面板侧从卡密映射不出 publisher，游戏层没有东西可拦；
# 而且 disabled 的公益卡本来就不导出到 cards.json（见 inc/sync.php），所以这里的判定与开关无关。
#
# 开关优先级（与账号维度那套完全一致）：
#   ① 环境变量 CN_SDK_BAN_CARD 非空 -> 只按它的值判定；
#   ② 文件 BANEXP_CARD_SWITCH_FILE 的内容。
# 真值 1/on/true/yes（大小写不敏感、去首尾空白）=> True：SDK 恢复拦卡密（旧行为）。
# 文件不存在 / 空 / 其它值 / 读失败 / 解析失败 / 任何异常 => False：不拦付费卡的卡密维度（新行为）。
# 每请求现读文件，线上写一个 1 就秒回退旧行为（不用重启、不用重新部署）；删掉文件即回到新行为。
BANEXP_CARD_SWITCH_FILE = (os.environ.get('CN_SDK_BAN_CARD_FILE')
                           or '/www/wwwroot/bapatch/cn_sdk_ban_card.txt')


def banexp_sdk_bans_card():
    """True = SDK 层也拦卡密（旧行为）；False = 不拦付费卡、交给游戏层（默认）。绝不抛。"""
    try:
        env = os.environ.get('CN_SDK_BAN_CARD')
        if env is not None and str(env).strip() != '':
            return _banexp_account_flag(env)
        try:
            with open(BANEXP_CARD_SWITCH_FILE, 'r', encoding='utf-8', errors='replace') as f:
                return _banexp_account_flag(f.read())
        except Exception:
            return False
    except Exception:
        return False


def banexp_dispatch(path, body, dev):
    """三个维度的封禁判定（只读、绝不抛）。命中返回响应 dict，未命中或出错返回 None。"""
    if not BANEXP_ON:
        return None
    try:
        st, row = banexp_state('device', dev)
        if st == 'active':
            return banexp_resp('device', row, dev)
        key, rec = banexp_card_of(path, body, dev)
        if key:
            st2, row2 = banexp_state('card', key)
            if st2 == 'active':
                # 卡密维度：
                #   · 公益卡（kind='free'）必须在这里拦 —— 面板映射不出它的 publisher，
                #     游戏层没有可拦的东西（NOTES.md §3）；
                #   · 付费卡默认放行给游戏层（开关 cn_sdk_ban_card.txt 为真时恢复旧行为）。
                try:
                    _free = (card_kind(rec) == KIND_FREE)
                except Exception:
                    _free = False
                if _free or banexp_sdk_bans_card():
                    return banexp_resp('card', row2, key)
                try:
                    w('BANEXP CARD SKIP(游戏层处理) %s until=%s' % (
                        _mask(key), row2.get('until_epoch')))
                except Exception:
                    pass
            try:
                pub = publisher_id(key, dev, rec)
            except Exception:
                pub = 0
            if pub:
                st3, row3 = banexp_state('account', str(pub))
                if st3 == 'active':
                    # 账号封禁：默认放行给游戏层（客户端才会弹官方封禁框）；
                    # 开关为真时才在这里拦（旧行为）。
                    if banexp_sdk_bans_account():
                        return banexp_resp('account', row3, str(pub))
                    try:
                        w('BANEXP ACCOUNT SKIP(游戏层处理) pub=%s until=%s'
                          % (str(pub), row3.get('until_epoch')))
                    except Exception:
                        pass
        return None
    except Exception:
        return None


try:
    w('=== BANEXP v1 === bans_db=%s ban_message=%s sdk_block_account=%s sdk_block_card=%s' % (
        BANEXP_DB, 'ok' if BANEXP_ON else 'MISSING(禁言文案模块缺失，bans 判定已跳过)',
        'yes' if banexp_sdk_bans_account() else 'no',
        'yes' if banexp_sdk_bans_card() else 'no'))
except Exception:
    pass
# <<< BAPATCH-BANEXP v1 <<<


# [PATCH-PY-20261118-cardtype] 卡类型：free=账号跟随设备 / paid=账号跟随卡密
KIND_PAID = "paid"
KIND_FREE = "free"


def card_kind(rec):
    k = str((rec or {}).get("kind") or "").strip().lower()
    return k if k in (KIND_PAID, KIND_FREE) else KIND_PAID


def migrate_cards(d):
    """幂等迁移：只补缺失字段，绝不覆盖已有值。返回是否有改动。"""
    changed = False
    cards = d.get("cards") if isinstance(d, dict) else None
    if not isinstance(cards, dict):
        return False
    for _k, rec in cards.items():
        if not isinstance(rec, dict):
            continue
        if "kind" not in rec:
            rec["kind"] = KIND_PAID
            changed = True
        if "max_devices" not in rec:
            rec["max_devices"] = 1 if rec.get("bind_one") else 0
            changed = True
        if "last_used_at" not in rec:
            rec["last_used_at"] = 0
            changed = True
    return changed


def publisher_id(card, device, rec=None):
    """paid: md5(card)  —— 算法一个字节都不能改（账号 2 = 314816420）
       free: md5('free:'+device) —— 每台设备一个独立账号"""
    seed = ("free:" + str(device)) if card_kind(rec) == KIND_FREE else str(card)
    return int(hashlib.md5(seed.encode()).hexdigest()[:8], 16) % 900000000 + 100000000


def login_check(card, rec, device):
    """-> (ok, code, msg)。成功时可能修改 rec['devices']（去重 append）。"""
    if not rec:
        return False, 400101, "卡密不正确"
    if rec.get("expire", 0) and rec["expire"] < time.time():
        return False, 400101, "卡密已过期"
    devs = rec.setdefault("devices", [])
    kind = card_kind(rec)
    if kind == KIND_FREE:
        if device and device not in devs:
            devs.append(device)          # 仅统计，不限制
        return True, 200, "OK"
    md = int(rec.get("max_devices", 0) or 0)
    if device and device not in devs:
        if md > 0 and len(devs) >= md:
            return False, 400101, "卡密已达到设备上限（最多 %d 台）" % md
        devs.append(device)
    return True, 200, "OK"


def pick_card_for_device(d, device):
    """quick-login 确定性选择：paid 优先 > last_used_at 倒序 > 卡密字典序。"""
    if not device:
        return None, None
    cands = []
    for key, rec in (d.get("cards") or {}).items():
        if not isinstance(rec, dict):
            continue
        if device not in (rec.get("devices") or []):
            continue
        if rec.get("expire", 0) and rec["expire"] < time.time():
            continue
        cands.append((0 if card_kind(rec) == KIND_PAID else 1,
                      -float(rec.get("last_used_at") or 0), str(key), rec))
    if not cands:
        return None, None
    cands.sort()
    return cands[0][2], cands[0][3]

def user_payload(card, device, rec=None):
    tpl = json.load(open(TEMPLATE))['Data']
    tok = hashlib.sha256((card + '|' + device).encode()).hexdigest()[:40]
    tpl['User']['Token'] = tok
    tpl['User']['ID'] = publisher_id(card, device, rec)
    tpl['Pass']['NickName'] = 'BA' + card[-4:]
    return tpl


# >>> BAPATCH-ORDER-PROBE v1 >>>
# Log-only probe for /order/* (stage 1). Behaviour is unchanged: the request
# still falls through to the existing fallback response. Never raises.
ORDER_LOG = '/www/wwwroot/ba_sdk/order_probe.log'
ORDER_OFF = '/www/wwwroot/ba_sdk/order_probe_off.txt'
ORDER_MAX_BYTES = 20 * 1024 * 1024


def _order_probe(handler, body):
    try:
        if os.path.exists(ORDER_OFF):
            return
        try:
            if os.path.isfile(ORDER_LOG) and os.path.getsize(ORDER_LOG) > ORDER_MAX_BYTES:
                os.replace(ORDER_LOG, ORDER_LOG + '.1')
        except Exception:
            pass
        raw = body or b''
        rec = {
            'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
            'epoch': time.time(),
            'client': '%s:%s' % (handler.client_address[0], handler.client_address[1]),
            'xff': handler.headers.get('X-Forwarded-For') or '',
            'real_ip': handler.headers.get('X-Real-IP') or '',
            'via': handler.headers.get('Via') or '',
            'method': handler.command,
            'path': handler.path,
            'body_len': len(raw),
            'body_sha256': hashlib.sha256(raw).hexdigest(),
        }
        hdrs = {}
        for k, v in handler.headers.items():
            hdrs[k] = v
        rec['headers'] = hdrs
        try:
            rec['body_text'] = raw.decode('utf-8')
        except Exception:
            rec['body_b64'] = base64.b64encode(raw).decode('ascii')
        with open(ORDER_LOG, 'a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            f.flush()
    except Exception as e:
        try:
            with open(ORDER_LOG, 'a') as f:
                f.write(json.dumps({'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
                                    'probe_error': repr(e)}) + '\n')
        except Exception:
            pass
# <<< BAPATCH-ORDER-PROBE v1 <<<


# >>> BAPATCH-ORDER-EP v1 >>>
# Real implementations of /order/products, /order/create, /order/detail.
# Config: /www/wwwroot/ba_sdk/pay.json (missing -> deny, safe default).
# Store:  /www/wwwroot/ba_sdk/orders.jsonl (append-only, one JSON per line).
ORDER_CFG = '/www/wwwroot/ba_sdk/pay.json'
ORDER_ALLOW = '/www/wwwroot/ba_sdk/allow_pay.txt'
ORDER_STORE = '/www/wwwroot/ba_sdk/orders.jsonl'
_ORDER_SEQ = [0]
_ORDER_LOCK = __import__('threading').Lock()
_ORDER_DEFAULTS = {
    'allow_pay': 0,
    'ok_code': 200,
    'fail_code': 40007,
    'pay_state_ok': 1,
    'delivery_state_ok': 1,
    'amount_mode': 'price_x100',
    'amount_fixed': 0,
    'order_prefix': 'SDK',
    'products': [],
}


def _order_cfg():
    """Read on EVERY request -> editing pay.json / allow_pay.txt takes effect
    immediately, no restart. Accepts both long keys and the short keys
    PayState / DeliveryState / Amount used by the ops sheet."""
    cfg = dict(_ORDER_DEFAULTS)
    try:
        with open(ORDER_CFG) as f:
            cfg.update(json.load(f) or {})
    except Exception:
        pass
    if 'PayState' in cfg:
        cfg['pay_state_ok'] = cfg['PayState']
    if 'DeliveryState' in cfg:
        cfg['delivery_state_ok'] = cfg['DeliveryState']
    if 'Amount' in cfg:
        cfg['amount_fixed'] = cfg['Amount']
        cfg['amount_mode'] = 'fixed'
    try:
        with open(ORDER_ALLOW) as f:
            cfg['allow_pay'] = 1 if f.read().strip() in ('1', 'on', 'true', 'yes') else 0
    except Exception:
        pass
    return cfg


def _order_products():
    cfg = _order_cfg()
    return {'Code': cfg['ok_code'], 'Msg': 'OK',
            'Data': {'Product': list(cfg.get('products') or [])}}


def _order_next_no(prefix):
    with _ORDER_LOCK:
        _ORDER_SEQ[0] = (_ORDER_SEQ[0] + 1) % 100000
        seq = _ORDER_SEQ[0]
    return '%s%s%05d' % (prefix, time.strftime('%Y%m%d%H%M%S'), seq)


def _order_price(product_id):
    for p in (_order_cfg().get('products') or []):
        try:
            if int(p.get('ID')) == int(product_id):
                return str(p.get('Price') or '0')
        except Exception:
            continue
    return '0'


def _order_amount(price_str):
    cfg = _order_cfg()
    if cfg.get('amount_mode') == 'fixed':
        return int(cfg.get('amount_fixed') or 0)
    try:
        return int(round(float(price_str) * 100))
    except Exception:
        return 0


def _order_save(rec):
    try:
        with open(ORDER_STORE, 'a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            f.flush()
    except Exception:
        pass


def _order_find(order_no):
    if not order_no:
        return None
    found = None
    try:
        with open(ORDER_STORE) as f:
            for line in f:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get('OrderNo') == order_no:
                    found = d
    except Exception:
        return None
    return found


def _order_make(payload, dev):
    """Return the Data dict for /order/create (already wrapped by caller)."""
    cfg = _order_cfg()
    if str(cfg.get('allow_pay', 0)) not in ('1', 'true', 'True', 'yes', 'on'):
        return {'Code': int(cfg['fail_code']), 'Msg': 'PAY_DISABLED', 'Data': None}

    pid = payload.get('ProductId')
    pay_type = str(payload.get('PayType') or '')
    price = _order_price(pid)
    order_no = _order_next_no(str(cfg.get('order_prefix') or 'SDK'))
    order = {
        'OrderNo': order_no,
        'Amount': _order_amount(price),
        'PayState': int(cfg['pay_state_ok']),
        'DeliveryState': int(cfg['delivery_state_ok']),
        'FirstPurchase': 0,
        'PayType': pay_type,
    }
    rec = dict(order)
    rec.update({'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
                'dev': dev, 'ProductId': pid,
                'ExtraData': payload.get('ExtraData'),
                'NotifyURL': payload.get('NotifyURL')})
    _order_save(rec)
    return {'Code': int(cfg['ok_code']), 'Msg': 'OK',
            'Data': {'Alipay': None, 'AlipayQRCode': None, 'Wechat': None,
                     'WechatQRCode': None, 'Bilibili': None, 'Order': order}}


def _order_detail(order_no):
    cfg = _order_cfg()
    rec = _order_find(order_no)
    order = None
    if rec:
        order = {k: rec.get(k) for k in ('OrderNo', 'Amount', 'PayState',
                                         'DeliveryState', 'FirstPurchase', 'PayType')}
    return {'Code': int(cfg['ok_code']), 'Msg': 'OK',
            'Data': {'Order': order, 'Level': '', 'Event': ''}}


def _order_dispatch(handler, path, body, dev):
    """Return a response dict, or None if the path is not ours."""
    if path == '/order/products':
        return _order_products()
    if path == '/order/create':
        try:
            payload = json.loads(body or b'{}')
        except Exception:
            payload = {}
        return _order_make(payload if isinstance(payload, dict) else {}, dev)
    if path == '/order/detail':
        try:
            payload = json.loads(body or b'{}')
        except Exception:
            payload = {}
        return _order_detail(str((payload or {}).get('OrderNo') or ''))
    return None
# <<< BAPATCH-ORDER-EP v1 <<<


class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def _send(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        raw = self.headers.get('content-length')
        try:
            n = int(str(raw).strip()) if raw not in (None, '') else 0
        except Exception:
            return None
        if n < 0 or n > MAX_SDK_BODY:
            return None
        return self.rfile.read(n) if n else b''

    def do_POST(self):
        body = self._body()
        if self.path.startswith('/order'):
            _order_probe(self, body)   # BAPATCH-ORDER-PROBE v1: log only, then continue
        dev = device_of(self)
        w('%s %s dev=%s\nBODY %s' % (time.strftime('%H:%M:%S'), self.path, dev,
                                     body[:500].decode('latin1')))
        path = self.path.split('?')[0]
        _order_resp = _order_dispatch(self, path, body, dev)   # BAPATCH-ORDER-EP v1
        if _order_resp is not None:
            self._send(_order_resp)
            return

        # BAPATCH-DEVBAN v1: 设备封禁早于卡密校验（只拦 3 个入口）
        if path in DEVICE_BAN_PATHS:
            _exp_resp = banexp_dispatch(path, body, dev)   # BAPATCH-BANEXP v1: 限时/永久封禁（三态共用文案）
            if _exp_resp is not None:
                self._send(_exp_resp)
                return
            _ban_resp = device_ban_resp(dev, path)
            if _ban_resp is not None:
                self._send(_ban_resp)
                return

        if path == '/common/config':
            cfg = json.load(open(CFG))

            def fix(o):
                if isinstance(o, str):
                    for a, b in (('static.bluearchive-cn.com', 'example.com'),
                                 ('gs-api.bluearchive-cn.com', 'example.com'),
                                 ('sdk-api.yostar.cn', 'example.com'),
                                 ('www.baidu.com', 'example.com')):
                        o = o.replace(a, b)
                    return o
                if isinstance(o, list):
                    return [fix(x) for x in o]
                if isinstance(o, dict):
                    return {k: fix(v) for k, v in o.items()}
                return o

            self._send(fix(cfg))
            return

        if path == '/user/login':
            try:
                j = json.loads(body or b'{}')
            except Exception:
                j = {}
            key = str(j.get('OpenID') or '').strip()
            d = load_cards()
            if migrate_cards(d):
                save_cards(d)
            rec = d['cards'].get(key)
            ok, code, msg = login_check(key, rec, dev)
            if not ok:
                w('LOGIN REJECT %s dev=%s kind=%s reason=%s' % (_mask(key), _mask(dev), card_kind(rec), msg))
                self._send({'Code': code, 'Msg': msg, 'Data': {}})
                return
            rec['last_used_at'] = time.time()
            save_cards(d)
            w('LOGIN OK %s dev=%s kind=%s devices=%d max=%s' % (
                _mask(key), _mask(dev), card_kind(rec), len(rec.get('devices') or []),
                rec.get('max_devices')))
            self._send({'Code': 200, 'Msg': 'OK', 'Data': user_payload(key, dev, rec)})
            return

        if path == '/user/quick-login':
            d = load_cards()
            if migrate_cards(d):
                save_cards(d)
            key, rec = pick_card_for_device(d, dev)
            if key is not None:
                ok, code, msg = login_check(key, rec, dev)
                if ok:
                    rec['last_used_at'] = time.time()
                    save_cards(d)
                    w('QUICK OK %s dev=%s kind=%s' % (_mask(key), _mask(dev), card_kind(rec)))
                    self._send({'Code': 200, 'Msg': 'OK', 'Data': user_payload(key, dev, rec)})
                    return
            self._send({'Code': 40003, 'Msg': '请输入卡密', 'Data': {}})
            return

        if path == '/user/detail':
            d = load_cards()
            key, rec = pick_card_for_device(d, dev)
            if key is not None:
                self._send({'Code': 200, 'Msg': 'OK', 'Data': user_payload(key, dev, rec)})
                return
            self._send({'Code': 200, 'Msg': 'OK', 'Data': {}})
            return
        if path == '/common/geo-ip':
            self._send({'Code': 200, 'Msg': 'OK', 'Data': {'Prov': '浙江省'}})
            return
        if path == '/health-game/duration':
            self._send({'Code': 110170, 'Msg': '用户已成年,不需要计时', 'Data': {}})
            return

        if path == '/heartbeat/pulse':
            self._send({'Code': 200, 'Msg': 'OK', 'Data': {'Delay': 3600}})
            return

        self._send({'Code': 200, 'Msg': 'OK', 'Data': {}})

    do_GET = do_POST

    def log_message(self, *a):
        pass


w('=== our sdk (card key) start === device_ban=%s' % (DEVICE_BAN_FILE,))
ThreadingHTTPServer(('127.0.0.1', 8080), H).serve_forever()