<?php
/**
 * inc/sync.php — MySQL（唯一真源） -> cards.json 同步引擎
 *
 * 为什么不让面板直接写 cards.json：
 *   1) php-fpm 以 www 身份跑，通常没有 /root/bapatch 的写权限；
 *   2) sdkcard.py 每次请求都重新读该文件，必须原子替换，否则会读到半个 JSON；
 *   3) 并发写会把文件写坏。
 * 所以：面板只写 MySQL；cron/sync_cards.php（root 或 www）负责导出。
 *
 * cards.json 目标结构（与 sdkcard.py 完全一致）：
 *   {"cards": {"<卡密>": {"devices": ["<DeviceID>"], "expire": 0, "bind_one": true,
 *                        "kind": "paid", "max_devices": 1, "last_used_at": 0,
 *                        "status": "active"}}}
 *
 * [GATEFIX 2026-11-18] 导出范围变了（只影响「被禁用的付费卡」，其它一律不变）：
 *   · 以前：只导 status='active' ⇒ 卡一被禁用就从 cards.json 消失 ⇒ SDK 回「卡密不正确」，
 *     玩家根本到不了游戏层。
 *   · 现在：active + **disabled 的付费卡**都导，并且每条记录带一个 status 字段
 *     （"active"|"disabled"，供排查；SDK 不读它）。
 *     disabled 的**公益卡**仍然不导（公益卡账号按设备算，做不出 publisher 映射，
 *     它的封禁继续由 SDK 层拦，见 NOTES.md §3）。
 *   · expire 语义一个字没动：过期仍由 sdkcard.py 的 login_check() 判，
 *     本文件不按 expire 过滤任何卡。
 *   · 同步同时做一件"对账"：把 disabled 的付费卡映射成 bans(kind='account') 行
 *     （桥只认这个维度）。失败一律**放行**，绝不反过来封人（NOTES.md §4）。
 *
 * 关键：sdkcard.py 自己也会在绑定新设备时写 cards.json（非原子，历史行为），
 * 所以本同步在导出前会先把 cards.json 里新出现的 device 合并回 MySQL，
 * 避免"同步一次就把用户刚绑的设备冲掉"。
 */

if (!defined('CARDADMIN')) {
    http_response_code(403);
    exit('403 Forbidden');
}

require_once __DIR__ . '/helpers.php';

/* ------------------------------------------------------------- 路径/锁 --- */

function sync_json_path()
{
    $p = (string)setting_get('cards_json_path', CARDS_JSON_PATH);
    return $p === '' ? CARDS_JSON_PATH : $p;
}

function sync_lock_path()
{
    $cands = array(
        APP_STATE_DIR . '/sync.lock',
        rtrim(sys_get_temp_dir(), '/\\') . DIRECTORY_SEPARATOR . 'ba_cardadmin_sync.lock',
    );
    foreach ($cands as $p) {
        $dir = dirname($p);
        if (is_dir($dir) && is_writable($dir)) {
            return $p;
        }
        if (!is_dir($dir) && @ensure_dir($dir) && is_writable($dir)) {
            return $p;
        }
    }
    return '';
}

function sync_flag_path()
{
    return APP_STATE_DIR . '/sync.request';
}

function sync_log_path()
{
    return APP_LOG_DIR . '/sync.log';
}

/** 同步过程日志（cron 里同时输出到 stdout） */
function sync_log_line($msg)
{
    $line = '[' . date('Y-m-d H:i:s') . '] ' . $msg;
    @ensure_dir(APP_LOG_DIR);
    @file_put_contents(sync_log_path(), $line . "\n", FILE_APPEND);
    if (PHP_SAPI === 'cli') {
        echo $line . "\n";
    }
    return $line;
}

/* ------------------------------------------------------------ 读 cards.json --- */

/**
 * @return array('exists'=>bool,'cards'=>array,'err'=>string,'bytes'=>int,'mtime'=>int)
 */
function sync_read_json($path)
{
    $res = array('exists' => false, 'cards' => array(), 'err' => '', 'bytes' => 0, 'mtime' => 0);
    if (!is_file($path)) {
        return $res;
    }
    $res['exists'] = true;
    $res['mtime']  = (int)@filemtime($path);
    $res['bytes']  = (int)@filesize($path);
    $raw = @file_get_contents($path);
    if ($raw === false) {
        $res['err'] = '无法读取 ' . $path;
        return $res;
    }
    if (trim($raw) === '') {
        /* 空文件：当成空卡密库（sdkcard.py 会报 JSON 错，所以我们要覆盖它） */
        return $res;
    }
    $data = json_decode($raw, true);
    if (!is_array($data)) {
        $res['err'] = 'cards.json 不是合法 JSON：' . json_last_error_msg();
        return $res;
    }
    if (isset($data['cards']) && is_array($data['cards'])) {
        $res['cards'] = $data['cards'];
    }
    return $res;
}

/* ------------------------------------------------------------ 孤儿检查 --- */

/**
 * 只读检查：cards.json 里有哪些卡密是 MySQL 不认识的
 * @return array('orphans'=>array,'json_cards'=>int,'err'=>string)
 */
function sync_orphan_check()
{
    $rd  = sync_read_json(sync_json_path());
    $out = array('orphans' => array(), 'json_cards' => 0, 'err' => $rd['err']);
    if ($rd['err'] !== '') {
        return $out;
    }
    $out['json_cards'] = count($rd['cards']);
    if (!$rd['cards']) {
        return $out;
    }
    $known = array();
    foreach (db_all('SELECT card_key FROM cards') as $r) {
        $known[(string)$r['card_key']] = true;
    }
    foreach ($rd['cards'] as $k => $v) {
        if (!isset($known[(string)$k])) {
            $out['orphans'][] = (string)$k;
        }
    }
    return $out;
}

/* ------------------------------------------------------------ 构造导出体 --- */

/** cards 表是否已有卡类型三列（ALTER 之前也能跑，缺列时按老逻辑导出） */
function sync_cards_has_type_cols()
{
    static $has = null;
    if ($has !== null) {
        return $has;
    }
    try {
        $n = (int)db_val(
            "SELECT COUNT(*) FROM information_schema.COLUMNS
              WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cards'
                AND COLUMN_NAME IN ('kind','max_devices','last_used_at')",
            array(),
            0
        );
        $has = ($n === 3);
    } catch (Throwable $e) {
        $has = false;
    }
    return $has;
}

/**
 * 纯函数：把「卡密行 + 设备表 + 旧 json」组装成 cards.json 的结构
 * 不碰数据库，方便单独测试（设备回灌只收集待写入的 [card_id, device]）。
 *
 * @param array $rows        待导出卡密行（active + disabled 的付费卡；含 id/card_key/status/
 *                           expire_at/bind_one[/kind/max_devices/last_used_at]）
 * @param array $dev_map     card_id => [device_id, ...]
 * @param array $old_cards   现有 cards.json 里的 cards 段
 * @param bool  $merge_devs  是否把旧 json 里多出来的设备并进来
 * @return array('cards'=>array,'pending_devices'=>array,'imported'=>int,'bad'=>array)
 */
function sync_make_payload($rows, $dev_map, $old_cards, $merge_devs = true)
{
    $out      = array();
    $pending  = array();
    $pending_lu = array();
    $imported = 0;
    $bad      = array();

    foreach ((array)$rows as $r) {
        $id  = isset($r['id']) ? (int)$r['id'] : 0;
        $key = isset($r['card_key']) ? (string)$r['card_key'] : '';

        if ($key === '' || slen($key) > 64) {
            $bad[] = '非法卡密（空或超长）id=' . $id;
            continue;
        }
        if (function_exists('mb_check_encoding') && !mb_check_encoding($key, 'UTF-8')) {
            $bad[] = '非法卡密（非 UTF-8）id=' . $id;
            continue;
        }

        $devices = array();
        if (isset($dev_map[$id]) && is_array($dev_map[$id])) {
            foreach ($dev_map[$id] as $dev) {
                $dev = (string)$dev;
                if ($dev !== '' && !in_array($dev, $devices, true)) {
                    $devices[] = $dev;
                }
            }
        }

        /* 把 sdkcard.py 侧新绑的设备并进来（只补不删） */
        if ($merge_devs && isset($old_cards[$key]) && is_array($old_cards[$key])) {
            $old_devs = isset($old_cards[$key]['devices']) && is_array($old_cards[$key]['devices'])
                ? $old_cards[$key]['devices'] : array();
            foreach ($old_devs as $dev) {
                if (!is_string($dev) || $dev === '') {
                    continue;
                }
                $dev = substr($dev, 0, 64);
                if (in_array($dev, $devices, true)) {
                    continue;
                }
                $devices[] = $dev;
                $pending[]  = array($id, $dev);
                $imported++;
            }
        }

        /* 卡类型 / 设备上限：MySQL 为准；ALTER 前缺列时按 bind_one 兼容 */
        $kind = (isset($r['kind']) && (string)$r['kind'] === 'free') ? 'free' : 'paid';
        $maxd = isset($r['max_devices'])
            ? (int)$r['max_devices']
            : ((isset($r['bind_one']) && (int)$r['bind_one'] === 1) ? 1 : 0);
        if ($kind === 'free') {
            $maxd = 0;
        }

        /* last_used_at：MySQL 与 cards.json 取较大者；json 更新则回写 MySQL（sdkcard 只写 json） */
        $lu_db   = isset($r['last_used_at']) ? dt_to_epoch($r['last_used_at']) : 0;
        $lu_json = 0;
        if (isset($old_cards[$key]) && is_array($old_cards[$key])
            && array_key_exists('last_used_at', $old_cards[$key])) {
            $lu_json = card_last_used_to_epoch($old_cards[$key]['last_used_at']);
        }
        $lu = max($lu_db, $lu_json);
        if ($lu_json > $lu_db && $id > 0) {
            $pending_lu[] = array($id, (int)$lu_json);
        }

        /* [GATEFIX] 卡状态：MySQL 原值透传（active|disabled）。
         * 只用于排查与对账；sdkcard.py 不读这个字段（它只读 devices/expire/kind/max_devices）。 */
        $st = (isset($r['status']) && (string)$r['status'] === 'disabled') ? 'disabled' : 'active';

        $out[$key] = array(
            'devices'      => array_values($devices),
            'expire'       => isset($r['expire_at']) ? (int)$r['expire_at'] : 0,
            'bind_one'     => ($maxd === 1),              /* legacy：由 max_devices 派生 */
            'kind'         => $kind,
            'max_devices'  => (int)$maxd,
            'last_used_at' => (int)$lu,                    /* epoch 秒，0=从未使用 */
            'status'       => $st,                         /* [GATEFIX] active|disabled */
        );
    }

    return array(
        'cards'              => $out,
        'pending_devices'    => $pending,
        'pending_last_used'  => $pending_lu,
        'imported'           => $imported,
        'bad'                => $bad,
    );
}

/* ============================================================================
 * [GATEFIX] 卡密封禁 -> 账号封禁行（bans 表）的对账
 *
 * 为什么同步进程要管封禁表：
 *   桥（account_auth_probe.py）只认 bans(kind='account', target=<publisher>)，
 *   而"这张卡被封"是按卡密记的。面板的封禁入口（inc/bans.php）在禁用时已经顺手写这条映射行；
 *   但面板上还有别的路径会把 cards.status 直接改成 'disabled'（卡密列表 / 批量操作 / 直接改库），
 *   它们不经过封禁入口 ⇒ 卡仍在 cards.json 里、SDK 不再拦卡密维度、桥也没有行 ⇒ 玩家进得去。
 *   同步是每分钟都跑、而且只有它知道"MySQL 里到底哪些卡 disabled"的那个进程，所以由它对账。
 *
 * 三条铁律（失败一律朝"放行"，见 NOTES.md §4）：
 *   ① 只碰 reason 以「卡密封禁」开头的 account 行；手工账号封禁一个字都不动；
 *   ② 只给 kind='paid' 的卡做映射；公益卡（free）跳过（它的账号按设备算，映射不出来）；
 *   ③ 异常 / 封禁表不可用 / 开关关闭 ⇒ 整段跳过，同步照常成功。
 *
 * 对账口径（幂等，重复跑没有副作用）：
 *   A. status='disabled' 的付费卡            -> 必须有一条 until_epoch=NULL 的映射行
 *   B. 卡不再 disabled 且没有生效中的卡密封禁 -> 删掉映射行
 *   C. 来源卡已经不在库里（publisher 不在"现有卡"集合里） -> 删掉残留映射行
 *      （删除 = 放行方向；这一条防的是"卡被删掉之后那个账号被永久封死"）
 * ========================================================================== */

/**
 * 对账开关：环境变量 CN_BANCARD_RECONCILE=0/off/false/no，或 off 文件存在 => 关闭。
 * 关掉之后同步只导 cards.json，不碰封禁表（回滚用，见 NOTES.md §5）。
 * @return bool
 */
function sync_bancard_on()
{
    static $on = null;
    if ($on !== null) {
        return $on;
    }
    $on  = true;
    $env = function_exists('getenv') ? getenv('CN_BANCARD_RECONCILE') : false;
    if ($env !== false && trim((string)$env) !== '') {
        $on = !in_array(strtolower(trim((string)$env)), array('0', 'off', 'false', 'no'), true);
        return $on;
    }
    $off = defined('BA_BANCARD_RECONCILE_OFF') ? (string)BA_BANCARD_RECONCILE_OFF : '';
    if ($off === '') {
        $off = '/www/wwwroot/bapatch/cn_bancard_reconcile_off.txt';
    }
    if ($off !== '' && is_file($off)) {
        $on = false;
    }
    return $on;
}

/**
 * 载入封禁表函数（inc/bans.php）。拿不到就返回 false：宁可不对账，也不能让同步挂掉。
 * @return bool
 */
function sync_bancard_lib()
{
    static $ok = null;
    if ($ok !== null) {
        return $ok;
    }
    $need = array('banexp_all', 'banexp_upsert', 'banexp_clear', 'banexp_is_active', 'bancard_reason');
    $miss = false;
    foreach ($need as $fn) {
        if (!function_exists($fn)) {
            $miss = true;
            break;
        }
    }
    if ($miss) {
        $inc = __DIR__ . '/bans.php';
        if (is_file($inc)) {
            try {
                require_once $inc;
            } catch (Throwable $e) {
                $ok = false;
                return $ok;
            }
        }
    }
    $ok = true;
    foreach ($need as $fn) {
        if (!function_exists($fn)) {
            $ok = false;
            break;
        }
    }
    return $ok;
}

/**
 * 付费卡的 publisher：`int(md5(卡密)[:8], 16) % 900000000 + 100000000`
 * 必须与 sdkcard.py 的 publisher_id() 逐位一致（对照算例见 NOTES.md §2）。
 * @param string $cardKey
 * @return int
 */
function sync_bancard_pub($cardKey)
{
    $key = (string)$cardKey;
    if ($key === '') {
        return 0;
    }
    return (int)(hexdec(substr(md5($key), 0, 8)) % 900000000) + 100000000;
}

/**
 * 映射行的 reason 前缀（只有这个前缀的行允许被本模块删）
 * @return string
 */
function sync_bancard_prefix()
{
    return defined('BANCARD_REASON_PREFIX') ? (string)BANCARD_REASON_PREFIX : '卡密封禁';
}

/**
 * 映射行的 reason（优先用 inc/bans.php 的 bancard_reason()，保证两个写入者逐字一致）
 * @param string $cardKey
 * @return string
 */
function sync_bancard_reason($cardKey)
{
    if (function_exists('bancard_reason')) {
        return bancard_reason((string)$cardKey);
    }
    $mask = function_exists('mask_card')
        ? mask_card((string)$cardKey)
        : substr(md5((string)$cardKey), 0, 8);
    return sync_bancard_prefix() . ' · ' . $mask;
}

/**
 * 对账主函数（只在不 dry-run 的实跑里调用）。
 *
 * @param array $status_of card_key => 'active'|'disabled'（MySQL 全量，不只是导出的那些）
 * @param array $kind_of   card_key => 'paid'|'free'（库还没有 kind 列时传空数组 = 全按 paid）
 * @param array $opts      source => cron/web/cron-dry
 * @return array('ok'=>bool,'enabled'=>bool,'error'=>string,'source'=>string,
 *               'added'=>int,'updated'=>int,'kept'=>int,'deleted'=>int,'manual'=>int,
 *               'skipped'=>int,'warnings'=>array)
 */
function sync_bancard_reconcile($status_of, $kind_of, $opts = array())
{
    $out = array(
        'ok' => false, 'enabled' => true, 'error' => '',
        'source' => (string)(isset($opts['source']) ? $opts['source'] : ''),
        'added' => 0, 'updated' => 0, 'kept' => 0, 'deleted' => 0,
        'manual' => 0, 'skipped' => 0, 'warnings' => array(),
    );
    if (!sync_bancard_on()) {
        $out['enabled'] = false;
        $out['ok']      = true;
        $out['error']   = '对账开关关闭（CN_BANCARD_RECONCILE / cn_bancard_reconcile_off.txt）';
        return $out;
    }
    if (!sync_bancard_lib()) {
        $out['error'] = 'inc/bans.php 不可用（拿不到 banexp_* / bancard_reason），本次没有对账';
        return $out;
    }
    try {
        $snap = banexp_all(true);
        if (empty($snap['ok']) || !isset($snap['rows']) || !is_array($snap['rows'])) {
            $out['error'] = '封禁表读不出来：' . (isset($snap['error']) ? (string)$snap['error'] : '未知原因');
            return $out;
        }
        $now    = time();
        $prefix = sync_bancard_prefix();
        $acct   = array();   /* publisher => 任意 kind='account' 行 */
        $cards  = array();   /* card_key  => 任意 kind='card' 行 */
        foreach ($snap['rows'] as $row) {
            $k = (string)$row['kind'];
            if ($k === 'account') {
                $acct[(string)$row['target']] = $row;
            } elseif ($k === 'card') {
                $cards[(string)$row['target']] = $row;
            }
        }

        /* 该有映射行的 / 库里还存在付费卡的 publisher 集合 */
        $expect = array();   /* publisher => card_key（status=disabled 的付费卡） */
        $key_of = array();   /* publisher => card_key（所有付费卡，删残留时反查卡密） */
        foreach ((array)$status_of as $key => $st) {
            $key  = (string)$key;
            $kind = (isset($kind_of[$key]) && (string)$kind_of[$key] === 'free') ? 'free' : 'paid';
            if ($kind !== 'paid') {
                $out['skipped']++;
                continue;
            }
            $pub = sync_bancard_pub($key);
            if ($pub <= 0) {
                $out['skipped']++;
                continue;
            }
            $ps          = (string)$pub;
            $key_of[$ps] = $key;
            if ((string)$st === 'disabled') {
                $expect[$ps] = $key;
            }
        }

        /* --- 先删不该留的（删除 = 放行方向；先删，后面写失败也不会留下过期行） --- */
        foreach ($acct as $ps => $row) {
            $ps = (string)$ps;
            if (isset($expect[$ps])) {
                continue;                      /* 该留着，下面统一补/更新 */
            }
            if (strpos((string)$row['reason'], $prefix) !== 0) {
                continue;                      /* 手工账号封禁：一个字都不碰 */
            }
            $why = '';
            if (!isset($key_of[$ps])) {
                $why = '来源卡已不在数据库里';
            } else {
                $ck = $key_of[$ps];
                $cr = isset($cards[$ck]) ? $cards[$ck] : null;
                if ($cr !== null && banexp_is_active($cr, $now)) {
                    $out['kept']++;            /* 限时卡密封禁还在生效：账号行必须留着 */
                    continue;
                }
                $why = '卡不再受限（status=' . (string)$status_of[$ck] . '，没有生效中的卡密封禁行）';
            }
            $rc = banexp_clear('account', $ps);
            if (!empty($rc['ok'])) {
                $out['deleted']++;
                sync_log_line('卡密封禁对账：删映射行 publisher=' . $ps . '（' . $why . '）');
            } else {
                $out['warnings'][] = '删映射行失败 publisher=' . $ps . '：' . $rc['error'];
            }
        }

        /* --- 该有的：补 / 纠正（disabled 是无限期，限时的残留要改成永久） --- */
        foreach ($expect as $ps => $ck) {
            $ps   = (string)$ps;
            $want = sync_bancard_reason($ck);
            $row  = isset($acct[$ps]) ? $acct[$ps] : null;
            if ($row !== null && strpos((string)$row['reason'], $prefix) !== 0) {
                $out['manual']++;
                $out['warnings'][] = 'publisher ' . $ps . ' 已有一条非卡密来源的账号封禁，没有覆盖它';
                continue;
            }
            if ($row !== null) {
                if ($row['until_epoch'] !== null || (string)$row['reason'] !== $want) {
                    $ru = banexp_upsert('account', $ps, null, $want, 'sync.php');
                    if (!empty($ru['ok'])) {
                        $out['updated']++;
                    } else {
                        $out['warnings'][] = '改映射行失败 publisher=' . $ps . '：' . $ru['error'];
                    }
                } else {
                    $out['kept']++;
                }
                continue;
            }
            $ru = banexp_upsert('account', $ps, null, $want, 'sync.php');
            if (!empty($ru['ok'])) {
                $out['added']++;
            } else {
                $out['warnings'][] = '写映射行失败 publisher=' . $ps . '：' . $ru['error'];
            }
        }

        $out['ok'] = true;
        return $out;
    } catch (Throwable $e) {
        $out['ok']    = false;
        $out['error'] = '卡密封禁对账异常：' . $e->getMessage();
        return $out;
    }
}

/**
 * 从 MySQL 读出待导出的卡密（active + disabled 的付费卡），组装 cards.json 结构。
 * [GATEFIX] 同时把"disabled 的付费卡"对账进 bans 表（失败只记 warning，绝不影响导出）。
 * @param array $opts import_devices=bool, no_mutate=bool, pretty=bool, source=string
 * @return array('ok'=>bool,'msg'=>string,'payload'=>string,'count'=>int,'imported'=>int,
 *               'orphans'=>array,'disabled'=>int,'exported_disabled'=>int,'bancard'=>array,'bad'=>array)
 */

/**
 * 从 MySQL 读出待导出的卡密（active + disabled 的付费卡），组装 cards.json 结构。
 * @param array $opts import_devices=bool 是否把 json 里的新设备合并回 MySQL
 * @return array('ok'=>bool,'msg'=>string,'payload'=>string,'count'=>int,'imported'=>int,
 *               'orphans'=>array,'disabled'=>int,'exported_disabled'=>int,'bancard'=>array,'bad'=>array)
 */
function sync_build($opts = array())
{
    $import_devices = !array_key_exists('import_devices', $opts) ? true : (bool)$opts['import_devices'];
    $mutate         = !array_key_exists('no_mutate', $opts) ? true : !(bool)$opts['no_mutate'];
    $json_path      = sync_json_path();
    $old            = sync_read_json($json_path);
    $bad            = array();

    /* 已有 JSON 里的 devices：按卡密索引 */
    $old_cards = $old['cards'];

    /* cards 表有没有卡类型三列（ALTER 之前也能跑，缺列时按老逻辑导出） */
    $has_type = sync_cards_has_type_cols();

    /* DB：所有卡密（含 disabled），用于识别 json 侧的孤儿卡密 + 给对账提供全量状态 */
    $all_cols = 'id, card_key, status' . ($has_type ? ', kind' : '');
    $all = db_all('SELECT ' . $all_cols . ' FROM cards');
    $by_key_status = array();
    $by_key_id     = array();
    $by_key_kind   = array();
    foreach ($all as $r) {
        $by_key_status[(string)$r['card_key']] = (string)$r['status'];
        $by_key_id[(string)$r['card_key']]     = (int)$r['id'];
        $by_key_kind[(string)$r['card_key']]   = isset($r['kind']) ? (string)$r['kind'] : 'paid';
    }

    /* DB：待导出卡密明细
     *
     * [GATEFIX] 导出范围：active + **disabled 的付费卡**。
     *   为什么 disabled 也要导：卡密封禁已经迁到游戏层（桥按 bans(kind='account') 回官方封禁包），
     *   如果还像以前那样"禁用即从 cards.json 消失"，SDK 会先回「卡密不正确」，
     *   玩家根本到不了游戏层，封禁文案永远看不到。
     *   为什么 disabled 的公益卡不导：公益卡的账号按设备算（publisher = md5('free:'+设备)），
     *   面板侧映射不出 publisher，游戏层没有可拦的东西，所以它的封禁**继续由 SDK 层拦**，
     *   行为与基线完全一致（卡从 cards.json 消失 ⇒ SDK 回「卡密不正确」）。见 NOTES.md §3。
     *   其它 status 值（以后要是加了 expired 之类）一律不导：语义与基线一致，不做猜测。 */
    $type_cols = $has_type ? ', kind, max_devices, last_used_at' : '';
    $where     = $has_type
        ? "(status = 'active' OR (status = 'disabled' AND kind = 'paid'))"
        : "status IN ('active', 'disabled')";   /* 没有 kind 列时全是老卡，等价于 paid */
    $rows = db_all(
        "SELECT id, card_key, status, expire_at, bind_one" . $type_cols . "
           FROM cards
          WHERE " . $where . "
          ORDER BY id ASC"
    );

    /* DB：设备表 */
    $dev_map = array();
    foreach (db_all('SELECT card_id, device_id FROM card_devices ORDER BY card_id ASC, id ASC') as $d) {
        $cid = (int)$d['card_id'];
        if (!isset($dev_map[$cid])) {
            $dev_map[$cid] = array();
        }
        $dev = (string)$d['device_id'];
        if ($dev !== '') {
            $dev_map[$cid][] = $dev;
        }
    }

    $payload_cards = array();
    $imported      = 0;
    $pending_devs  = array();

    $made = sync_make_payload($rows, $dev_map, $old_cards, $import_devices);
    $payload_cards = $made['cards'];
    $imported      = $made['imported'];
    $bad           = array_merge($bad, $made['bad']);
    $pending_devs  = $made['pending_devices'];
    $pending_lu    = $made['pending_last_used'];

    /* 把 sdkcard.py 侧新绑定的设备补回 MySQL（只补不删） */
    if ($mutate && $pending_devs) {
        foreach ($pending_devs as $pd) {
            try {
                db_run(
                    'INSERT IGNORE INTO card_devices (card_id, device_id, bound_at, last_seen_at)
                     VALUES (?, ?, NOW(), NOW())',
                    array((int)$pd[0], (string)$pd[1])
                );
            } catch (Throwable $e) {
                /* 单条失败不影响整体 */
            }
        }
    }

    /* 把 sdkcard.py 侧更新的 last_used_at 回写 MySQL（只前进，不后退） */
    if ($mutate && $pending_lu && sync_cards_has_type_cols()) {
        foreach ($pending_lu as $pl) {
            try {
                $ts = date('Y-m-d H:i:s', (int)$pl[1]);
                db_run(
                    'UPDATE cards SET last_used_at = ?
                      WHERE id = ? AND (last_used_at IS NULL OR last_used_at < ?)',
                    array($ts, (int)$pl[0], $ts)
                );
            } catch (Throwable $e) {
                /* 单条失败不影响整体 */
            }
        }
    }

    /* 孤儿：在 cards.json 里存在但 MySQL 完全没有 -> 不导出（MySQL 为真源），计数提醒 */
    $orphans = array();
    foreach ($old_cards as $k => $v) {
        if (!isset($by_key_status[$k])) {
            $orphans[] = (string)$k;
        }
    }
    $disabled_cnt = 0;
    foreach ($by_key_status as $k => $st) {
        if ((string)$st !== 'active' && !isset($payload_cards[$k])) {
            $disabled_cnt++;
        }
    }

    /* [GATEFIX] 本次导出的 disabled 卡数（付费卡，带 status 字段），与上面那个口径分开：
     *   disabled          = 被禁用但**没导出**的卡（= disabled 的公益卡，基线"禁用跳过"口径）
     *   exported_disabled = 导出的 disabled 卡（付费卡） */
    $exported_disabled = 0;
    foreach ($payload_cards as $k => $rec) {
        if (isset($rec['status']) && $rec['status'] === 'disabled') {
            $exported_disabled++;
        }
    }

    /* [GATEFIX] 卡密封禁对账：让"MySQL 里 disabled 的付费卡"在 bans 表里都有 kind='account' 行。
     * 只在不 dry-run 的实跑里做（沿用 sync_build 既有的 no_mutate 约定）；
     * 任何失败都只记 warning，绝不让同步失败，也绝不因此封人。 */
    $bancard = array('ok' => true, 'enabled' => false, 'skipped' => true,
        'error' => '', 'warnings' => array(), 'added' => 0, 'updated' => 0,
        'kept' => 0, 'deleted' => 0, 'manual' => 0);
    if ($mutate) {
        $bancard = sync_bancard_reconcile($by_key_status, $by_key_kind, array(
            'source' => isset($opts['source']) ? (string)$opts['source'] : 'sync',
        ));
        if (!empty($bancard['error'])) {
            sync_log_line('卡密封禁对账跳过：' . $bancard['error']);
        }
        if (!empty($bancard['warnings'])) {
            foreach ((array)$bancard['warnings'] as $wn) {
                sync_log_line('卡密封禁对账：' . $wn);
            }
        }
    }

    $out = array('cards' => $payload_cards);
    $flags = JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES;
    if (!empty($opts['pretty'])) {
        $flags |= JSON_PRETTY_PRINT;
    }
    $json = json_encode($out, $flags);
    if ($json === false) {
        return array(
            'ok' => false, 'msg' => 'JSON 编码失败：' . json_last_error_msg(),
            'payload' => '', 'count' => 0, 'imported' => $imported,
            'orphans' => $orphans, 'disabled' => $disabled_cnt,
            'exported_disabled' => $exported_disabled, 'bancard' => $bancard, 'bad' => $bad,
        );
    }

    return array(
        'ok'       => true,
        'msg'      => 'ok',
        'payload'  => $json,
        'count'    => count($payload_cards),
        'imported' => $imported,
        'orphans'  => $orphans,
        'disabled' => $disabled_cnt,
        'exported_disabled' => $exported_disabled,
        'bancard'  => $bancard,
        'bad'      => $bad,
    );
}

/* --------------------------------------------------------------- 主流程 --- */

/**
 * 执行一次同步：MySQL -> cards.json（原子替换 + flock）
 *
 * @param array $opts
 *   dry_run        bool  只计算不写文件
 *   force          bool  允许在首次同步时丢弃 json 孤儿卡密
 *   import_devices bool  默认 true
 *   source         string 触发来源（cron/web/manual）
 * @return array('ok'=>bool,'msg'=>string,...)
 */
function sync_cards($opts = array())
{
    $dry_run = !empty($opts['dry_run']);
    $force   = !empty($opts['force']);
    $source  = isset($opts['source']) ? (string)$opts['source'] : 'cron';

    $json_path = sync_json_path();
    $dir       = dirname($json_path);

    if (!$dry_run && !is_dir($dir)) {
        return array('ok' => false, 'msg' => '目标目录不存在：' . $dir);
    }

    $lock_path = sync_lock_path();
    if ($lock_path === '') {
        return array('ok' => false, 'msg' => '找不到可写的锁文件目录（state/ 与临时目录都不可写）');
    }
    $fp = @fopen($lock_path, 'c');
    if ($fp === false) {
        return array('ok' => false, 'msg' => '无法打开锁文件：' . $lock_path);
    }
    @chmod($lock_path, 0666);   /* www 与 root 都要能开，这只是锁文件 */
    if (!flock($fp, LOCK_EX | LOCK_NB)) {
        fclose($fp);
        return array('ok' => false, 'msg' => '另一个同步进程正在运行，稍后再试');
    }

    try {
        /* 首次同步保护：json 里还有 MySQL 不认识的卡密时默认不覆盖，
           逼管理员先去"从 cards.json 导入现有卡密"，避免一上手就把别人的卡全删掉。 */
        $last_sync = setting_get('last_sync_at', '');
        if (!$force && $last_sync === '') {
            $chk = sync_orphan_check();
            if (count($chk['orphans']) > 0) {
                $msg = '首次同步被拦截：cards.json 中有 ' . count($chk['orphans']) . ' 个卡密在数据库里不存在'
                     . '（' . implode(', ', array_map('mask_card', array_slice($chk['orphans'], 0, 5)))
                     . (count($chk['orphans']) > 5 ? ' 等' : '') . '）。'
                     . '请先在「系统设置 → 从 cards.json 导入现有卡密」里导入，'
                     . '或给 cron 加 --force 参数表示"以数据库为准、直接丢弃"。';
                sync_log_line('同步被拦截(' . $source . ')：孤儿卡密 ' . count($chk['orphans']) . ' 个');
                return array('ok' => false, 'msg' => $msg, 'orphans' => $chk['orphans'], 'count' => 0);
            }
        }

        $built = sync_build(array(
            'import_devices' => !isset($opts['import_devices']) ? true : (bool)$opts['import_devices'],
            'no_mutate'      => $dry_run,
            'pretty'         => true,
            'source'         => $source,          /* [GATEFIX] 对账日志里带上触发来源 */
        ));
        if (!$built['ok']) {
            sync_log_line('同步失败(' . $source . ')：' . $built['msg']);
            return array('ok' => false, 'msg' => $built['msg']);
        }

        $orphans = $built['orphans'];
        $bc      = isset($built['bancard']) && is_array($built['bancard'])
            ? $built['bancard'] : array();
        if ($dry_run) {
            sync_log_line('DRY-RUN(' . $source . ')：将导出 ' . $built['count'] . ' 个卡密（其中禁用 '
                . (int)$built['exported_disabled'] . ' 个），'
                . bytes_human(strlen($built['payload'])) . '，孤儿 ' . count($orphans)
                . '（dry-run 不做卡密封禁对账）');
            return array(
                'ok' => true, 'msg' => 'dry-run 完成（未写文件）',
                'count' => $built['count'], 'bytes' => strlen($built['payload']),
                'orphans' => $orphans, 'imported' => $built['imported'],
                'exported_disabled' => (int)$built['exported_disabled'],
                'preview' => substr($built['payload'], 0, 600),
            );
        }

        /* 备份现有文件（best effort） */
        if (is_file($json_path) && is_readable($json_path)) {
            $bak_dir = APP_STATE_DIR;
            if (@ensure_dir($bak_dir) && is_writable($bak_dir)) {
                @copy($json_path, $bak_dir . '/cards.backup.json');
            }
        }

        /* 软链接提醒：rename 会替换链接本身（不是它指向的文件），主人要知道 */
        if (@is_link($json_path)) {
            sync_log_line('警告：' . $json_path . ' 是软链接，本次 rename 会把链接替换成普通文件');
        }

        $wr = atomic_write($json_path, $built['payload'], 0644);
        if ($wr !== true) {
            sync_log_line('写入失败(' . $source . ')：' . $wr);
            return array('ok' => false, 'msg' => '写入 cards.json 失败：' . $wr
                . '（cron 若以 root 运行而 web 无权限属正常，请看 cron 日志）');
        }

        /* 回读校验：确认落盘的是完整 JSON */
        $check = sync_read_json($json_path);
        if ($check['err'] !== '') {
            /* 尝试从备份恢复 */
            $bak = APP_STATE_DIR . '/cards.backup.json';
            if (is_file($bak) && is_readable($bak)) {
                @copy($bak, $json_path);
            }
            sync_log_line('回读校验失败(' . $source . ')：' . $check['err'] . '（已尝试恢复备份）');
            return array('ok' => false, 'msg' => '写入后校验失败：' . $check['err']);
        }

        $now = time();
        setting_set('last_sync_at', $now);
        setting_set('last_sync_count', $built['count']);
        setting_set('last_sync_bytes', strlen($built['payload']));
        setting_set('last_sync_source', $source);
        setting_set('last_sync_msg', 'ok');

        sync_log_line('同步成功(' . $source . ')：导出 ' . $built['count'] . ' 个卡密（其中禁用 '
            . (int)$built['exported_disabled'] . ' 个，带 status 字段）'
            . bytes_human(strlen($built['payload'])) . '，合并设备 ' . $built['imported']
            . '，丢弃孤儿 ' . count($orphans) . '，禁用跳过 ' . $built['disabled']
            . '，卡密封禁对账 新增 ' . (int)(isset($bc['added']) ? $bc['added'] : 0)
            . ' / 更新 ' . (int)(isset($bc['updated']) ? $bc['updated'] : 0)
            . ' / 保留 ' . (int)(isset($bc['kept']) ? $bc['kept'] : 0)
            . ' / 删残留 ' . (int)(isset($bc['deleted']) ? $bc['deleted'] : 0)
            . '（手工封禁未覆盖 ' . (int)(isset($bc['manual']) ? $bc['manual'] : 0)
            . '，公益卡跳过 ' . (int)(isset($bc['skipped']) ? $bc['skipped'] : 0) . '）');

        // >>> AUTOBIND 2026-11-18 BEGIN >>>
        // 卡密首次登录后把「卡密 -> 玩家」补成 card_players(source='auto')。
        // 这张表过去只有面板手动写入，导致新卡登录建号后在面板上"无归属"。
        // 红线：任何异常一律吞掉，绝不因此让卡密同步失败。
        try {
            if (!function_exists('player_autobind_cards')) {
                require_once __DIR__ . '/players.php';
            }
            $ab = player_autobind_cards();
            if (!empty($ab['bound']) || !empty($ab['fixed']) || !empty($ab['error'])) {
                /* [DEVFIX2] bound 已经把"纠正"那一条也算进去了，这里减掉，否则同一张卡被数两次 */
                sync_log_line('卡密自动绑定：新增 ' . ((int)$ab['bound'] - (int)$ab['fixed']) . ' 条，纠正 ServerId '
                    . (int)$ab['fixed'] . ' 条（扫描 ' . (int)$ab['scanned']
                    . '，跳过 ' . (int)$ab['skipped'] . '）'
                    . ($ab['error'] !== '' ? '，注意：' . $ab['error'] : ''));
            }
        } catch (Throwable $e) {
            sync_log_line('卡密自动绑定异常（已放行）：' . $e->getMessage());
        }
        // <<< AUTOBIND 2026-11-18 END <<<

        return array(
            'ok'       => true,
            'msg'      => '同步成功',
            'count'    => $built['count'],
            'bytes'    => strlen($built['payload']),
            'imported' => $built['imported'],
            'orphans'  => $orphans,
            'disabled' => $built['disabled'],
            'exported_disabled' => (int)$built['exported_disabled'],
            'bancard'  => $bc,
        );
    } catch (Throwable $e) {
        sync_log_line('同步异常(' . $source . ')：' . $e->getMessage());
        return array('ok' => false, 'msg' => '同步异常：' . $e->getMessage());
    } finally {
        @flock($fp, LOCK_UN);
        @fclose($fp);
    }
}

/* ------------------------------------------------------ 从 json 反向导入 --- */

/**
 * 把 cards.json 里 MySQL 不认识的卡密导入 MySQL（一次性迁移用）
 * @return array('ok'=>bool,'msg'=>string,'added'=>int,'devices'=>int,'skipped'=>int)
 */
function sync_import_orphans($dry_run = false)
{
    $json_path = sync_json_path();
    $rd = sync_read_json($json_path);
    if ($rd['err'] !== '') {
        return array('ok' => false, 'msg' => $rd['err'], 'added' => 0, 'devices' => 0, 'skipped' => 0);
    }
    if (!$rd['exists']) {
        return array('ok' => false, 'msg' => 'cards.json 不存在：' . $json_path, 'added' => 0, 'devices' => 0, 'skipped' => 0);
    }

    $known = array();
    foreach (db_all('SELECT card_key FROM cards') as $r) {
        $known[(string)$r['card_key']] = true;
    }

    $added = 0;
    $devs  = 0;
    $skip  = 0;
    $admin = function_exists('current_admin') && current_admin() ? current_admin()['username'] : 'cron';

    foreach ($rd['cards'] as $key => $rec) {
        $key = (string)$key;
        if ($key === '' || slen($key) > 64) {
            $skip++;
            continue;
        }
        if (isset($known[$key])) {
            $skip++;
            continue;
        }
        if ($dry_run) {
            $added++;
            continue;
        }
        $expire   = is_array($rec) && isset($rec['expire']) ? (int)$rec['expire'] : 0;
        $bind_one = is_array($rec) && array_key_exists('bind_one', $rec)
            ? (!empty($rec['bind_one']) ? 1 : 0) : 1;
        /* 卡类型三列（ALTER 后）从 json 里带回，避免恢复时丢类型 */
        $kind = (is_array($rec) && isset($rec['kind']) && (string)$rec['kind'] === 'free') ? 'free' : 'paid';
        $maxd = (is_array($rec) && array_key_exists('max_devices', $rec))
            ? card_max_devices_norm($kind, (int)$rec['max_devices'])
            : (int)$bind_one;
        $bind_one = card_bind_one_from_max($maxd);
        $lu = (is_array($rec) && array_key_exists('last_used_at', $rec))
            ? card_last_used_to_epoch($rec['last_used_at']) : 0;
        try {
            if (sync_cards_has_type_cols()) {
                db_run(
                    'INSERT INTO cards (card_key, status, expire_at, bind_one, kind, max_devices, last_used_at,
                                        created_at, created_by, note, login_count, last_login_at, last_login_device)
                     VALUES (?, ?, ?, ?, ?, ?, ?, NOW(), ?, ?, 0, NULL, NULL)',
                    array($key, 'active', $expire, $bind_one, $kind, $maxd,
                          $lu > 0 ? date('Y-m-d H:i:s', $lu) : null,
                          substr($admin, 0, 64), '从 cards.json 导入')
                );
            } else {
                db_run(
                    'INSERT INTO cards (card_key, status, expire_at, bind_one, created_at, created_by, note,
                                        login_count, last_login_at, last_login_device)
                     VALUES (?, ?, ?, ?, NOW(), ?, ?, 0, NULL, NULL)',
                    array($key, 'active', $expire, $bind_one, substr($admin, 0, 64), '从 cards.json 导入')
                );
            }
            $cid = db_insert_id();
            $added++;
            if (is_array($rec) && isset($rec['devices']) && is_array($rec['devices'])) {
                foreach ($rec['devices'] as $d) {
                    if (!is_string($d) || $d === '') {
                        continue;
                    }
                    db_run(
                        'INSERT IGNORE INTO card_devices (card_id, device_id, bound_at, last_seen_at)
                         VALUES (?, ?, NOW(), NOW())',
                        array($cid, substr($d, 0, 64))
                    );
                    $devs++;
                }
            }
        } catch (Throwable $e) {
            $skip++;
        }
    }

    if (!$dry_run) {
        sync_log_line('从 cards.json 导入：新增 ' . $added . ' 个卡密，' . $devs . ' 台设备，跳过 ' . $skip);
    }
    return array('ok' => true, 'msg' => 'ok', 'added' => $added, 'devices' => $devs, 'skipped' => $skip);
}

/* --------------------------------------------------------- 面板手动同步 --- */

/**
 * 面板点"立即同步"：
 *   - 如果当前 PHP 进程能写 cards.json 目录 -> 直接同步
 *   - 否则写请求标记，由 cron（root）下一分钟内执行
 */
function sync_run_from_web()
{
    $json_path = sync_json_path();
    $dir       = dirname($json_path);
    $can_write = is_dir($dir) && is_writable($dir);
    if (is_file($json_path) && is_writable($json_path) && !$can_write) {
        $can_write = true;   /* 目录不可写但文件可写：atomic_write 会退化成 copy */
    }

    if ($can_write) {
        $r = sync_cards(array('source' => 'web', 'force' => false));
        return $r;
    }

    /* 写请求标记，cron 会优先处理 */
    if (!@ensure_dir(APP_STATE_DIR) || !is_writable(APP_STATE_DIR)) {
        return array('ok' => false, 'msg' => '当前进程对 ' . $dir . ' 与 ' . APP_STATE_DIR
            . ' 都没有写权限；请用 cron 定时同步，或把 cron 频率调快');
    }
    $payload = json_encode(array(
        'ts'   => time(),
        'by'   => function_exists('current_admin') && current_admin() ? current_admin()['username'] : 'web',
        'ip'   => function_exists('client_ip') ? client_ip() : '',
    ), JSON_UNESCAPED_UNICODE);
    $wr = atomic_write(sync_flag_path(), (string)$payload, 0644);
    if ($wr !== true) {
        return array('ok' => false, 'msg' => '写同步标记失败：' . $wr);
    }
    return array(
        'ok'  => true,
        'msg' => '已提交同步请求（当前 PHP 用户无权写 cards.json）。'
               . 'cron 会在 60 秒内执行，卡密随后生效。',
    );
}

function sync_flag_pending()
{
    return is_file(sync_flag_path());
}

function sync_flag_clear()
{
    if (is_file(sync_flag_path())) {
        @unlink(sync_flag_path());
        return true;
    }
    return false;
}

/** 读标记内容（用于审计） */
function sync_flag_info(){
    if (!is_file(sync_flag_path())) {
        return null;
    }
    $raw = @file_get_contents(sync_flag_path());
    if ($raw === false) {
        return null;
    }
    $j = json_decode($raw, true);
    return is_array($j) ? $j : array();
}

/* ------------------------------------------------------- 面板按钮统一处理 --- */

/**
 * 处理面板上的同步类 POST（dashboard/settings 共用）
 * 调用前页面必须已登录并校验过 CSRF。
 * @return array|null array(ok=>bool,msg=>string)
 */
function sync_do_web_action()
{
    $act = isset($_POST['action']) ? (string)$_POST['action'] : '';
    if ($act === 'sync_now') {
        $r = sync_run_from_web();
        if (function_exists('audit_log')) {
            audit_log('sync.manual', 'cards.json', ($r['ok'] ? '成功：' : '失败：') . $r['msg']);
        }
        return $r;
    }
    if ($act === 'import_json') {
        $r = sync_import_orphans(false);
        $msg = $r['ok']
            ? ('从 cards.json 导入完成：新增 ' . $r['added'] . ' 个卡密、' . $r['devices']
               . ' 台设备，跳过 ' . $r['skipped'] . ' 个已存在')
            : ('导入失败：' . $r['msg']);
        if (function_exists('audit_log')) {
            audit_log('sync.import_json', 'cards.json', $msg);
        }
        return array('ok' => $r['ok'], 'msg' => $msg);
    }
    return null;
}

/* -------------------------------------------------------------- 状态查询 --- */

/** 给界面用的同步状态快照（只读） */
function sync_status()
{
    $json_path = sync_json_path();
    $st = array(
        'json_path'   => $json_path,
        'exists'      => is_file($json_path),
        'readable'    => is_readable($json_path),
        'writable'    => is_writable($json_path),
        'dir_writable' => is_dir(dirname($json_path)) ? is_writable(dirname($json_path)) : false,
        'mtime'       => 0,
        'bytes'       => 0,
        'file_cards'  => null,
        'db_active'   => 0,
        'db_all'      => 0,
        'last_sync_at' => (int)setting_int('last_sync_at', 0),
        'last_count'  => (int)setting_int('last_sync_count', 0),
        'last_source' => (string)setting_get('last_sync_source', ''),
        'flag_pending' => sync_flag_pending(),
        'lock_path'   => sync_lock_path(),
    );
    if ($st['exists']) {
        $st['mtime'] = (int)@filemtime($json_path);
        $st['bytes'] = (int)@filesize($json_path);
        $rd = sync_read_json($json_path);
        if ($rd['err'] === '') {
            $st['file_cards'] = count($rd['cards']);
        } else {
            $st['file_cards'] = 'JSON 错误：' . $rd['err'];
        }
    }
    try {
        $st['db_all']     = (int)db_val('SELECT COUNT(*) FROM cards', array(), 0);
        $st['db_active']  = (int)db_val("SELECT COUNT(*) FROM cards WHERE status = 'active'", array(), 0);
    } catch (Throwable $e) {
        /* ignore */
    }
    return $st;
}
