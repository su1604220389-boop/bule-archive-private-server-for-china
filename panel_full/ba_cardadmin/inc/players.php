<?php
/**
 * inc/players.php —— 玩家域聚合层
 *
 * 数据来源（三个，各有分工，互不越权）：
 *   1. Shittim admin API  —— 账号/等级/货币/角色/邮件，是**唯一真源**，也是唯一写入通道
 *   2. MySQL ba_cardadmin —— 卡密、绑定的设备、`card_players` 手工绑定
 *   3. /www/wwwroot/bapatch/data/accounts.db（只读）—— 桥接侧账号镜像：设备号、登录次数、最后登录
 *
 * 不碰 /root/shittim.sqlite3（www 无权限，且写库约束散在 C# 里）。
 */

if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}

require_once __DIR__ . '/db.php';
require_once __DIR__ . '/ba.php';

/** 桥接账号库路径（只读） */
function player_accounts_db_path()
{
    if (defined('BA_ACCOUNTS_DB') && BA_ACCOUNTS_DB !== '') {
        return (string)BA_ACCOUNTS_DB;
    }
    $custom = function_exists('setting_get') ? (string)setting_get('ba_accounts_db', '') : '';
    return $custom !== '' ? $custom : '/www/wwwroot/bapatch/data/accounts.db';
}

/**
 * 读桥接账号镜像（只读）。失败返回 []，面板降级但不崩。
 * @return array publisher_account_id => row
 */
function player_bridge_accounts()
{
    static $rows = null;
    if ($rows !== null) {
        return $rows;
    }
    $rows = array();
    $path = player_accounts_db_path();
    if (!is_file($path) || !is_readable($path)) {
        return $rows;
    }
    if (!class_exists('PDO') || !in_array('sqlite', PDO::getAvailableDrivers(), true)) {
        return $rows;
    }
    try {
        $pdo = new PDO('sqlite:' . $path, null, null, array(
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::SQLITE_ATTR_OPEN_FLAGS  => PDO::SQLITE_OPEN_READONLY,
        ));
        foreach ($pdo->query('SELECT * FROM accounts') as $r) {
            if (isset($r['publisher_account_id'])) {
                $rows[(string)$r['publisher_account_id']] = $r;
            }
        }
    } catch (Throwable $e) {
        $rows = array();
    }
    return $rows;
}

/** 桥接账号库是否可用（给设置页自检用） */
function player_bridge_status()
{
    $path = player_accounts_db_path();
    $out = array(
        'path'    => $path,
        'exists'  => is_file($path),
        'readable' => is_readable($path),
        'rows'    => 0,
        'error'   => '',
        'has_pdo_sqlite' => class_exists('PDO') && in_array('sqlite', PDO::getAvailableDrivers(), true),
    );
    if ($out['has_pdo_sqlite'] && $out['readable']) {
        $out['rows'] = count(player_bridge_accounts());
    } elseif (!$out['has_pdo_sqlite']) {
        $out['error'] = 'PHP 未启用 pdo_sqlite 扩展';
    } elseif (!$out['exists']) {
        $out['error'] = '文件不存在';
    } else {
        $out['error'] = 'PHP 用户无读权限（' . $path . '）';
    }
    return $out;
}

/* ------------------------------------------------- 卡密 ↔ 玩家 绑定关系 --- */

/** 确保 card_players 表存在（面板首次访问即自建，不依赖 install.php 重跑） */
function player_ensure_tables()
{
    static $done = false;
    if ($done) {
        return;
    }
    $done = true;
    try {
        db_run("CREATE TABLE IF NOT EXISTS `card_players` (
            `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
            `card_id` INT UNSIGNED NOT NULL,
            `publisher_account_id` BIGINT NOT NULL DEFAULT 0,
            `server_id` BIGINT NOT NULL DEFAULT 0,
            `source` VARCHAR(16) NOT NULL DEFAULT 'manual' COMMENT 'manual / auto / device',
            `note` VARCHAR(255) NOT NULL DEFAULT '',
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `created_by` VARCHAR(64) NOT NULL DEFAULT '',
            PRIMARY KEY (`id`),
            UNIQUE KEY `uk_card_players_card` (`card_id`),
            KEY `idx_card_players_pub` (`publisher_account_id`),
            KEY `idx_card_players_sid` (`server_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='卡密与玩家的绑定'");

        db_run("CREATE TABLE IF NOT EXISTS `panel_ops` (
            `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `batch_id` CHAR(16) NOT NULL DEFAULT '',
            `action` VARCHAR(32) NOT NULL DEFAULT '',
            `targets` TEXT NULL,
            `payload` TEXT NULL,
            `ok_count` INT NOT NULL DEFAULT 0,
            `fail_count` INT NOT NULL DEFAULT 0,
            `admin_name` VARCHAR(64) NOT NULL DEFAULT '',
            `ip` VARCHAR(45) NOT NULL DEFAULT '',
            `ts` INT UNSIGNED NOT NULL DEFAULT 0,
            PRIMARY KEY (`id`),
            KEY `idx_panel_ops_batch` (`batch_id`),
            KEY `idx_panel_ops_ts` (`ts`),
            KEY `idx_panel_ops_action` (`action`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='玩家域写操作批次记录'");
    } catch (Throwable $e) {
        /* 表已存在或数据库不可用：不阻断页面 */
    }
}

/** 记一批玩家域写操作（发奖/改货币/封禁/GM 命令） */
function panel_op_log($action, $targets, $payload, $okCount, $failCount, $batchId = '')
{
    player_ensure_tables();
    if ($batchId === '') {
        $batchId = substr(bin2hex(random_bytes(6)), 0, 12);
    }
    $admin = (function_exists('current_admin') && current_admin()) ? current_admin()['username'] : '';
    $ip    = function_exists('client_ip') ? client_ip() : '';
    try {
        db_run(
            'INSERT INTO panel_ops (batch_id, action, targets, payload, ok_count, fail_count, admin_name, ip, ts)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            array(
                $batchId, (string)$action,
                is_array($targets) ? implode(',', $targets) : (string)$targets,
                is_array($payload) ? json_encode($payload, JSON_UNESCAPED_UNICODE) : (string)$payload,
                (int)$okCount, (int)$failCount, (string)$admin, (string)$ip, time(),
            )
        );
    } catch (Throwable $e) {
        /* 记不上不阻断主流程 */
    }
    return $batchId;
}

/** 最近的玩家域操作 */
function panel_op_recent($limit = 20)
{
    player_ensure_tables();
    try {
        return db_all('SELECT * FROM panel_ops ORDER BY id DESC LIMIT ' . (int)$limit);
    } catch (Throwable $e) {
        return array();
    }
}

/** card_id => ['publisher_account_id','server_id','source','note','created_at'] */
function player_card_bindings()
{
    player_ensure_tables();
    $out = array();
    try {
        foreach (db_all('SELECT * FROM card_players') as $r) {
            $out[(int)$r['card_id']] = $r;
        }
    } catch (Throwable $e) {
        return array();
    }
    return $out;
}

/** 绑定一张卡到某个玩家（覆盖式） */
function player_bind_card($cardId, $publisherAccountId, $serverId, $source = 'manual', $note = '', $by = '')
{
    player_ensure_tables();
    $cardId = (int)$cardId;
    if ($cardId <= 0) {
        return array('ok' => false, 'error' => '卡密 id 无效');
    }
    try {
        db_run(
            'INSERT INTO card_players (card_id, publisher_account_id, server_id, source, note, created_by, created_at)
             VALUES (?, ?, ?, ?, ?, ?, NOW())
             ON DUPLICATE KEY UPDATE publisher_account_id = VALUES(publisher_account_id),
                 server_id = VALUES(server_id), source = VALUES(source), note = VALUES(note),
                 created_by = VALUES(created_by)',
            array($cardId, (int)$publisherAccountId, (int)$serverId, (string)$source, (string)$note, (string)$by)
        );
        return array('ok' => true, 'error' => '');
    } catch (Throwable $e) {
        return array('ok' => false, 'error' => $e->getMessage());
    }
}

function player_unbind_card($cardId)
{
    player_ensure_tables();
    try {
        db_run('DELETE FROM card_players WHERE card_id = ?', array((int)$cardId));
        return array('ok' => true);
    } catch (Throwable $e) {
        return array('ok' => false, 'error' => $e->getMessage());
    }
}

/* ------------------------------------------------------- 玩家列表聚合 --- */

/**
 * 全部玩家（以 Shittim 账号表为准），合并桥接镜像与卡密绑定。
 *
 * @param array $filters ['q'=>搜索词, 'state'=>Normal|Dormant|..., 'has_card'=>bool]
 * @return array ['ok','error','ms','rows','bot_hidden']
 */
function player_roster($filters = array())
{
    $out = array('ok' => false, 'error' => '', 'ms' => 0, 'rows' => array(), 'total' => 0);

    $r = ba_accounts();
    $out['ms'] = $r['ms'];
    if (!$r['ok'] || !is_array($r['data'])) {
        $out['error'] = $r['error'] !== '' ? $r['error'] : '读取账号列表失败';
        return $out;
    }

    $bridge  = player_bridge_accounts();
    $binding = player_card_bindings();

    // card_id => card row（含设备数）
    $cards = array();
    try {
        foreach (db_all('SELECT c.id, c.card_key, c.status, c.expire_at, c.bind_one, c.note,
                                (SELECT COUNT(*) FROM card_devices d WHERE d.card_id = c.id) AS dev_count
                         FROM cards c') as $c) {
            $cards[(int)$c['id']] = $c;
        }
    } catch (Throwable $e) {
        $cards = array();
    }

    $byPub    = array();   // publisher_account_id => [card...]
    $byServer = array();   // server_id => [card...]
    foreach ($binding as $cardId => $b) {
        if (!isset($cards[$cardId])) {
            continue;
        }
        $entry = array(
            'card_id'   => $cardId,
            'card_key'  => (string)$cards[$cardId]['card_key'],
            'status'    => (string)$cards[$cardId]['status'],
            'expire_at' => (int)$cards[$cardId]['expire_at'],
            'dev_count' => (int)$cards[$cardId]['dev_count'],
            'source'    => (string)$b['source'],
        );
        $byPub[(string)(int)$b['publisher_account_id']][] = $entry;
        $byServer[(string)(int)$b['server_id']][] = $entry;
    }

    $q     = isset($filters['q']) ? trim((string)$filters['q']) : '';
    $state = isset($filters['state']) ? trim((string)$filters['state']) : '';
    $only  = isset($filters['has_card']) ? (bool)$filters['has_card'] : false;

    $rows = array();
    foreach ($r['data'] as $a) {
        $sid = (int)$a['serverId'];
        $pub = isset($a['publisherAccountId']) ? (string)(int)$a['publisherAccountId'] : '';

        $br = ($pub !== '' && isset($bridge[$pub])) ? $bridge[$pub] : null;

        $myCards = array();
        if ($pub !== '' && isset($byPub[$pub])) {
            $myCards = $byPub[$pub];
        } elseif (isset($byServer[(string)$sid])) {
            $myCards = $byServer[(string)$sid];
        }

        $row = array(
            'server_id'      => $sid,
            'nickname'       => (string)$a['nickname'],
            'call_name'      => isset($a['callName']) ? (string)$a['callName'] : '',
            'level'          => (int)$a['level'],
            'exp'            => (int)$a['exp'],
            'comment'        => isset($a['comment']) ? (string)$a['comment'] : '',
            'publisher_id'   => $pub,
            'state'          => isset($a['state']) ? (string)$a['state'] : '',
            'vip'            => isset($a['vipLevel']) ? (int)$a['vipLevel'] : 0,
            'last_connect'   => isset($a['lastConnectTime']) ? (string)$a['lastConnectTime'] : '',
            'create_date'    => isset($a['createDate']) ? (string)$a['createDate'] : '',
            'unread_mail'    => isset($a['unReadMailCount']) ? (int)$a['unReadMailCount'] : 0,
            'device'         => $br !== null && isset($br['device_unique_id']) ? (string)$br['device_unique_id'] : '',
            'dev_id'         => $br !== null && isset($br['dev_id']) ? (string)$br['dev_id'] : '',
            'bridge_id'      => $br !== null && isset($br['server_id']) ? (string)$br['server_id'] : '',
            'login_count'    => $br !== null && isset($br['login_count']) ? (int)$br['login_count'] : 0,
            'bridge_last'    => $br !== null && isset($br['last_login_at']) ? (string)$br['last_login_at'] : '',
            'cards'          => $myCards,
            'card_keys'      => array(),
        );
        foreach ($myCards as $mc) {
            $row['card_keys'][] = $mc['card_key'];
        }

        if ($state !== '' && strcasecmp($row['state'], $state) !== 0) {
            continue;
        }
        if ($only && !$myCards) {
            continue;
        }
        if ($q !== '') {
            $hay = $row['nickname'] . ' ' . $row['publisher_id'] . ' ' . $row['device'] . ' '
                 . implode(' ', $row['card_keys']) . ' ' . $sid;
            if (stripos($hay, $q) === false) {
                continue;
            }
        }
        $rows[] = $row;
    }

    usort($rows, function ($x, $y) {
        return strcmp($y['last_connect'], $x['last_connect']);
    });

    $out['ok']    = true;
    $out['rows']  = $rows;
    $out['total'] = count($rows);
    return $out;
}

/** 单个玩家的合并视图 */
function player_one($serverId)
{
    $r = ba_account_detail($serverId);
    if (!$r['ok'] || !is_array($r['data'])) {
        return array('ok' => false, 'error' => $r['error'] !== '' ? $r['error'] : '读取失败', 'data' => null);
    }
    $d   = $r['data'];
    $pub = isset($d['publisherAccountId']) ? (string)(int)$d['publisherAccountId'] : '';

    $bridge = player_bridge_accounts();
    $br     = ($pub !== '' && isset($bridge[$pub])) ? $bridge[$pub] : null;

    $binding = player_card_bindings();
    $myCards = array();
    try {
        $cards = db_all('SELECT id, card_key, status, expire_at FROM cards');
        foreach ($cards as $c) {
            $cid = (int)$c['id'];
            if (!isset($binding[$cid])) {
                continue;
            }
            $b = $binding[$cid];
            if ((string)(int)$b['publisher_account_id'] === $pub || (int)$b['server_id'] === (int)$serverId) {
                $myCards[] = array(
                    'card_id'   => $cid,
                    'card_key'  => (string)$c['card_key'],
                    'status'    => (string)$c['status'],
                    'expire_at' => (int)$c['expire_at'],
                    'source'    => (string)$b['source'],
                );
            }
        }
    } catch (Throwable $e) {
        $myCards = array();
    }

    return array(
        'ok'     => true,
        'error'  => '',
        'detail' => $d,
        'bridge' => $br,
        'cards'  => $myCards,
        'state'  => isset($d['state']) ? (string)$d['state'] : '',
    );
}

/* ----------------------------------------------------------- 状态/展示 --- */

/** AccountState 数字与文案。Dormant 被我们借作封禁（见 BAPATCH-BAN） */
function player_state_map()
{
    return array(
        0 => array('WaitingSignIn', '未签到'),
        1 => array('Normal', '正常'),
        2 => array('Dormant', '已封禁'),
        3 => array('Comeback', '回归'),
        4 => array('Newbie', '新手'),
    );
}

function player_state_label($state)
{
    foreach (player_state_map() as $id => $v) {
        if (strcasecmp($state, $v[0]) === 0) {
            return $v[1];
        }
    }
    return $state === '' ? '—' : $state;
}

function player_is_banned($state)
{
    return strcasecmp((string)$state, 'Dormant') === 0;
}

/** 封号 / 解封（写 State：2=封禁，1=正常） */
function player_set_ban($serverId, $ban)
{
    $r = ba_account_update($serverId, array('State' => $ban ? 2 : 1));
    if (!$r['ok']) {
        return array('ok' => false, 'error' => $r['error']);
    }
    return array('ok' => true, 'error' => '');
}

/* --------------------------------------------------------- 货币摘要 --- */

/** @return array name => amount（按 CurrencyTypes 名） */
function player_currency_dict($serverId)
{
    $r = ba_account_currencies($serverId);
    if (!$r['ok'] || !is_array($r['data'])) {
        return array();
    }
    return $r['data'];
}

/** 面板顶部常用的四个数：青辉石 / 金币 / 体力 / 精通币 */
function player_currency_key($dict, $names, $default = 0)
{
    foreach ((array)$names as $n) {
        if (isset($dict[$n])) {
            return (int)$dict[$n];
        }
    }
    return $default;
}

/** 时间字符串（ISO或 SQLite 风格）→ 友好显示 */
function player_dt($s, $def = '—')
{
    $s = trim((string)$s);
    if ($s === '' || $s === '0001-01-01T00:00:00' || $s === '0001-01-01 00:00:00') {
        return $def;
    }
    $ts = strtotime($s);
    if ($ts === false || $ts <= 0) {
        return $def;
    }
    return date('m-d H:i', $ts);
}

/* ============================================================================
 * 角色排除名单（双层保险的第二层）
 *
 * 第一层在服务端：ExcelTableService 的 BAPATCH-CLIENTROSTER 已经把下面这些角色
 * 从 CharacterExcelT 里剔掉了，所以 !giveall / !give / 卡池 / 商店 / 活动奖励
 * 都不可能再发放它们。
 *
 * 这一层是给面板自己用的：万一有人手打角色 id、或者绕过按钮直接调命令，
 * 面板在提交前先拦下来，给出明确提示，而不是让服务端静默丢弃。
 *
 * 这 23 个 id 是这么来的（2026-11-17 用客户端那份 ExcelDB 实测）：
 *   CharacterAcademyTagsDBSchema（客户端"名单"）253 个
 *   ∩ CharacterDBSchema（客户端"角色数据"）7223 行
 *   = 234 个客户端真正能解析的角色
 *   差集 23 个 ⇒ 客户端遇到就中止登录同步
 *
 * 客户端更新后，改 state/character_denylist.txt（一行一个 id，# 注释）
 * 就能覆盖这份内置默认值，不用改代码。
 * ========================================================================== */

function ba_denied_character_ids()
{
    static $ids = null;
    if ($ids !== null) {
        return $ids;
    }

    $ids = array(
        10099,
        10127, 10128, 10129, 10130, 10131, 10132, 10133, 10134, 10135, 10136, 10137, 10138,
        16018, 16019,
        20050, 20051, 20052, 20053, 20054, 20055, 20056, 20057,
    );

    $path = (defined('APP_STATE_DIR') ? APP_STATE_DIR : sys_get_temp_dir()) . '/character_denylist.txt';
    if (is_file($path) && is_readable($path)) {
        $extra = array();
        foreach ((array)@file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
            $line = trim($line);
            if ($line === '' || $line[0] === '#') {
                continue;
            }
            $n = (int)$line;
            if ($n > 0) {
                $extra[$n] = $n;
            }
        }
        if ($extra) {
            $ids = array_values(array_unique(array_merge($ids, array_values($extra))));
            sort($ids);
        }
    }

    return $ids;
}

function ba_is_denied_character($id)
{
    $id = (int)$id;
    return $id > 0 && in_array($id, ba_denied_character_ids(), true);
}

/**
 * 校验一组邮件/包裹附件：角色类附件不允许命中排除名单。
 * @param array $parcels [['type'=>'Character','id'=>10000,'amount'=>1], ...]
 * @return string 空串 = 通过；否则是给用户看的中文错误
 */
function ba_validate_parcels($parcels)
{
    foreach ((array)$parcels as $p) {
        $t = isset($p['type']) ? (string)$p['type'] : '';
        $id = isset($p['id']) ? (int)$p['id'] : 0;
        if ($t === 'Character' && ba_is_denied_character($id)) {
            return '角色 ' . $id . ' 是当前客户端无法解析的角色（会导致登录同步失败），已被面板拦下。'
                 . '服务端也已排除，请换一个角色 id。';
        }
    }
    return '';
}

/**
 * 校验一条 GM 命令：不允许 `give Character <被排除的id> ...` 这类写法。
 * 只做保守匹配——命中就直接拒绝，宁可多拦一次也不要放过去。
 * @return string 空串 = 通过
 */
function ba_validate_command($command)
{
    $cmd = ' ' . preg_replace('/\s+/', ' ', trim((string)$command)) . ' ';
    if (stripos($cmd, 'character') === false) {
        return '';
    }

    // 把命令里的数字全抓出来，逐个比对排除名单。
    // 只有命令里出现 character 时才做这个检查，避免误伤 `give Currency 4 1000` 这类。
    if (preg_match_all('/\b(\d{4,6})\b/', $cmd, $m)) {
        foreach ($m[1] as $num) {
            if (ba_is_denied_character((int)$num)) {
                return '命令里出现了角色 ' . $num . '，它是当前客户端无法解析的角色（会导致登录同步失败），已被面板拦下。';
            }
        }
    }
    return '';
}

/* ================================================================== *
 *  [AUTOBIND 2026-11-18] 卡密 -> 玩家 自动绑定（source='auto'）
 *
 *  为什么需要它：cards 表里**没有**"绑定账号"这一列；卡密与玩家的关系
 *  只存在 card_players 表里，而这张表过去**只有面板手动写入** ⇒ 新卡
 *  第一次登录虽然会建号（桥 + Shittim），但没有任何代码把这条关系记下来，
 *  面板上就永远显示"该卡无归属"（实测：8 号卡 <REDACTED_CONTACT> 登录后建了
 *  accounts 10000000006 / Shittim ServerId 7，card_players 里却没有它）。
 *
 *  身份是**可推导**的，不用猜：
 *      User.ID = hexdec(md5(卡密)[0:8]) % 900000000 + 100000000
 *  桥侧 account_auth_probe.py、Shittim 的 PublisherAccountId、面板三边同一条
 *  公式，实测对得上：
 *      11111111111 -> 314816420
 *      12222222222 -> 854071516
 *      <REDACTED_CONTACT> -> 819675745
 *
 *  安全规则（宁可少绑，绝不绑错）：
 *    1. 只处理客户端能用的格式 ^1[0-9]{10}$（16 位老卡不推导）；
 *    2. 只有派生出的 publisher 在 Shittim 里**确实有账号**时才绑；
 *    3. 已存在的 manual 绑定**永不覆盖**；
 *    4. 已是同一条 auto 绑定 -> 跳过（幂等，不写库）。
 * ================================================================== */

/** 卡密 -> 派生出的 publisher 账号 id。不合法/不兼容 -> 0 */
function card_derived_pub($cardKey)
{
    $k = trim((string)$cardKey);
    if ($k === '' || !preg_match('/^1[0-9]{10}$/', $k)) {
        return 0;
    }
    if (PHP_INT_SIZE < 8) {                 /* 32 位 PHP 上 hexdec 会变 float，宁可不绑 */
        return 0;
    }
    $n = hexdec(substr(md5($k), 0, 8));     /* 8 个 hex = 最大 0xFFFFFFFF，64 位 int 安全 */
    if (!is_int($n)) {
        return 0;
    }
    return (int)($n % 900000000) + 100000000;
}

/**
 * 补全"卡密 -> 玩家"的缺失绑定。
 *
 * @param int  $limit   本次最多扫多少张卡（按 id 倒序，新卡优先）
 * @param bool $dryRun  只统计不写库
 * @return array ['scanned','bound','skipped','error']
 */
function player_autobind_cards($limit = 500, $dryRun = false)
{
    player_ensure_tables();
    $out = array('scanned' => 0, 'bound' => 0, 'fixed' => 0, 'skipped' => 0, 'error' => '');

    $cards = array();
    try {
        $cards = db_all('SELECT id, card_key FROM cards ORDER BY id DESC LIMIT ' . (int)$limit);
    } catch (Throwable $e) {
        $out['error'] = $e->getMessage();
        return $out;
    }
    if (!$cards) {
        return $out;
    }

    /* publisher -> server_id（以 Shittim 账号表为准；读不到就整体跳过，不瞎绑） */
    $sidOf = array();
    try {
        $acc = ba_accounts();
        if (is_array($acc) && !empty($acc['ok']) && is_array($acc['data'])) {
            foreach ($acc['data'] as $a) {
                if (!isset($a['publisherAccountId']) || !isset($a['serverId'])) {
                    continue;
                }
                $pub = (string)(int)$a['publisherAccountId'];
                if ($pub !== '' && $pub !== '0') {
                    $sidOf[$pub] = (int)$a['serverId'];
                }
            }
        }
    } catch (Throwable $e) {
        $sidOf = array();
    }
    if (!$sidOf) {
        $out['error'] = '读不到 Shittim 账号表，本次跳过（避免绑错）';
        return $out;
    }

    $existing = player_card_bindings();
    $todo = array();

    foreach ($cards as $c) {
        $out['scanned']++;
        $cid = (int)$c['id'];
        $pub = card_derived_pub(isset($c['card_key']) ? $c['card_key'] : '');
        if ($pub <= 0) {
            $out['skipped']++;
            continue;
        }
        if (!isset($sidOf[(string)$pub])) {                       /* Shittim 里没这个号 -> 不绑 */
            $out['skipped']++;
            continue;
        }
        $wantSid = (int)$sidOf[(string)$pub];
        $cur = isset($existing[$cid]) ? $existing[$cid] : null;
        if ($cur) {
            $src = isset($cur['source']) ? (string)$cur['source'] : '';
            if ($src === 'manual') {                              /* 手动绑定最高优先级 */
                $out['skipped']++;
                continue;
            }
            if ((int)$cur['publisher_account_id'] === $pub && (int)$cur['server_id'] === $wantSid) {
                $out['skipped']++;                                /* 已是最新，不写库 */
                continue;
            }
            if ((int)$cur['publisher_account_id'] === $pub) {
                /* [SIDFIX 2026-11-18] 账号没变但 ServerId 变了 —— 删号重建会让 Shittim
                 * 重新分配 ServerId（实测 7 -> 8 -> 9），旧逻辑只看 publisher 就跳过，
                 * 结果 server_id 永远停在过期值上。这里改成"纠正确保一致"。 */
                $out['fixed']++;
            }
        }
        $todo[$cid] = array($pub, $wantSid);
    }

    if ($dryRun) {
        $out['bound'] = count($todo);
        return $out;
    }

    foreach ($todo as $cid => $p) {
        $r = player_bind_card($cid, $p[0], $p[1], 'auto', '卡密登录自动绑定');
        if (!empty($r['ok'])) {
            $out['bound']++;
        }
    }
    return $out;
}
/* ==================[ AUTOBIND 2026-11-18 END ]================== */
