<?php
/**
 * inc/ba.php — Blue Archive 服务端（Shittim）admin API 客户端
 *
 * 面板与游戏服务端之间只走这一层：
 *   · 所有写操作 → Shittim 内置 /api/admin/*（走它自己的 EF Core，派生字段/JSON 形状由它保证）
 *   · 从不直接写 /root/shittim.sqlite3
 *
 * 鉴权：Shittim 的 AdminAuthAttribute 在"配了 key"时强制要求 X-Admin-Key（环回也不例外），
 * 所以这里必须带上。key 从 config.php 的 BA_ADMIN_KEY 读，读不到再回落到 settings 表。
 *
 * 约定：所有函数都不抛异常，失败返回 ['ok'=>false, ...]，调用方负责展示。
 */

if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}

require_once __DIR__ . '/db.php';

/* ---------------------------------------------------------------- 配置 --- */

/** 服务端连接配置（base / key / timeout / 是否启用） */
function ba_cfg($reload = false)
{
    static $cfg = null;
    if ($cfg !== null && !$reload) {
        return $cfg;
    }

    $base = defined('BA_ADMIN_BASE') ? (string)BA_ADMIN_BASE : '';
    $key  = defined('BA_ADMIN_KEY') ? (string)BA_ADMIN_KEY : '';

    if ($base === '' && function_exists('setting_get')) {
        try {
            $base = (string)setting_get('ba_admin_base', '');
        } catch (Throwable $e) {
            $base = '';
        }
    }
    if ($key === '' && function_exists('setting_get')) {
        try {
            $key = (string)setting_get('ba_admin_key', '');
        } catch (Throwable $e) {
            $key = '';
        }
    }

    if ($base === '') {
        $base = 'http://127.0.0.1:5000';
    }

    $cfg = array(
        'base'    => rtrim($base, '/'),
        'key'     => $key,
        'timeout' => 8,
        'cache'   => defined('APP_STATE_DIR') ? APP_STATE_DIR . '/bacache' : sys_get_temp_dir() . '/bacache',
    );
    return $cfg;
}

/** 本机 127.0.0.1 到底该连哪个端口（5000 / 5100 都行，5000 是网关口） */
function ba_admin_base()
{
    $c = ba_cfg();
    return $c['base'];
}

/* ------------------------------------------------------------ 底层 HTTP --- */

/**
 * 向 Shittim admin API 发一个请求。
 *
 * @param string     $method GET|POST
 * @param string     $path   以 / 开头的路径，如 /api/admin/accounts
 * @param array|null $body   POST 的 JSON body
 * @param array      $opts   ['timeout'=>int, 'raw'=>bool]
 * @return array ['ok'=>bool,'status'=>int,'data'=>mixed,'error'=>string,'ms'=>int,'url'=>string]
 */
function ba_http($method, $path, $body = null, $opts = array())
{
    $c       = ba_cfg();
    $url     = $c['base'] . $path;
    $timeout = isset($opts['timeout']) ? (int)$opts['timeout'] : (int)$c['timeout'];
    $method  = strtoupper($method);
    $t0      = microtime(true);

    $headers = array('Accept: application/json');
    if ($c['key'] !== '') {
        $headers[] = 'X-Admin-Key: ' . $c['key'];
    }

    $res = array('ok' => false, 'status' => 0, 'data' => null, 'error' => '', 'ms' => 0, 'url' => $url);

    if (function_exists('curl_init')) {
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 3);
        curl_setopt($ch, CURLOPT_TIMEOUT, $timeout);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, false);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        if ($method === 'POST') {
            $payload = json_encode($body === null ? new stdClass() : $body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
            $headers[] = 'Content-Type: application/json';
            curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        } else {
            curl_setopt($ch, CURLOPT_HTTPGET, true);
        }
        $raw = curl_exec($ch);
        $res['status'] = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        if ($raw === false) {
            $res['error'] = '连接服务端失败：' . curl_error($ch);
        }
        curl_close($ch);
    } else {
        $hdr = implode("\r\n", $headers);
        $ctx = stream_context_create(array('http' => array(
            'method'        => $method,
            'header'        => $hdr,
            'content'       => ($method === 'POST')
                ? json_encode($body === null ? new stdClass() : $body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)
                : '',
            'timeout'       => $timeout,
            'ignore_errors' => true,
        )));
        $raw = @file_get_contents($url, false, $ctx);
        if (isset($http_response_header[0]) && preg_match('/\s(\d{3})\s/', $http_response_header[0], $m)) {
            $res['status'] = (int)$m[1];
        }
        if ($raw === false) {
            $res['error'] = '连接服务端失败（file_get_contents）';
        }
    }

    $res['ms'] = (int)round((microtime(true) - $t0) * 1000);

    if (isset($raw) && $raw !== false && $raw !== null) {
        $decoded = json_decode($raw, true);
        $res['data'] = ($decoded === null && trim((string)$raw) !== '') ? (string)$raw : $decoded;
        if ($res['error'] === '') {
            if ($res['status'] >= 200 && $res['status'] < 300) {
                $res['ok'] = true;
            } elseif ($res['status'] === 0) {
                $res['error'] = '服务端无响应';
            } elseif (is_array($decoded) && isset($decoded['error'])) {
                $res['error'] = (string)$decoded['error'];
            } else {
                $res['error'] = 'HTTP ' . $res['status'];
            }
        }
    } elseif ($res['error'] === '') {
        $res['error'] = '服务端无响应';
    }

    return $res;
}

function ba_get($path, $query = array(), $opts = array())
{
    if ($query) {
        $path .= (strpos($path, '?') === false ? '?' : '&') . http_build_query($query);
    }
    return ba_http('GET', $path, null, $opts);
}

function ba_post($path, $body = array(), $opts = array())
{
    return ba_http('POST', $path, $body, $opts);
}

/* -------------------------------------------------------------- 缓存层 --- */

function ba_cache_dir()
{
    $c = ba_cfg();
    $d = $c['cache'];
    if (!is_dir($d)) {
        @mkdir($d, 0775, true);
    }
    return $d;
}

function ba_cache_get($key, $ttl = 300)
{
    $f = ba_cache_dir() . '/' . preg_replace('/[^a-z0-9_.-]/i', '_', $key) . '.json';
    if (!is_file($f)) {
        return null;
    }
    if ($ttl > 0 && (time() - (int)@filemtime($f)) > $ttl) {
        return null;
    }
    $j = @file_get_contents($f);
    if ($j === false) {
        return null;
    }
    $v = json_decode($j, true);
    return is_array($v) ? $v : null;
}

function ba_cache_put($key, $value)
{
    $f = ba_cache_dir() . '/' . preg_replace('/[^a-z0-9_.-]/i', '_', $key) . '.json';
    @file_put_contents($f, json_encode($value, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES), LOCK_EX);
    return $value;
}

function ba_cache_flush($prefix = '')
{
    $d = ba_cache_dir();
    $n = 0;
    foreach ((array)@glob($d . '/*.json') as $f) {
        if ($prefix === '' || strpos(basename($f), $prefix) === 0) {
            if (@unlink($f)) {
                $n++;
            }
        }
    }
    return $n;
}

/* ------------------------------------------------------------ 只读接口 --- */

function ba_status($opts = array())
{
    return ba_get('/api/admin/status', array(), $opts);
}

/** 全部账号（含 publisherAccountId / devId / state） */
function ba_accounts($opts = array())
{
    return ba_get('/api/admin/accounts', array(), $opts);
}

function ba_account_detail($serverId, $opts = array())
{
    return ba_get('/api/admin/account/' . (int)$serverId . '/detail', array(), $opts);
}

function ba_account_currencies($serverId, $opts = array())
{
    return ba_get('/api/admin/account/' . (int)$serverId . '/currencies', array(), $opts);
}

function ba_account_items($serverId, $opts = array())
{
    return ba_get('/api/admin/account/' . (int)$serverId . '/items', array(), $opts);
}

function ba_account_characters($serverId, $opts = array())
{
    return ba_get('/api/admin/account/' . (int)$serverId . '/characters', array(), $opts);
}

function ba_account_mails($serverId, $opts = array())
{
    return ba_get('/api/admin/account/' . (int)$serverId . '/mails', array(), $opts);
}

/* ------------------------------------------------- 静态数据（带磁盘缓存） --- */

/** 货币 id => 名称（[{id,name}] 来自 /static/currencies） */
function ba_static_currencies($opts = array())
{
    $c = ba_cache_get('static_currencies', 3600);
    if ($c !== null) {
        return array('ok' => true, 'data' => $c, 'error' => '', 'cached' => true);
    }
    $r = ba_get('/api/admin/static/currencies', array(), $opts);
    if ($r['ok'] && is_array($r['data'])) {
        ba_cache_put('static_currencies', $r['data']);
    } elseif ($c !== null) {
        $r['data'] = $c;
    }
    return $r;
}

/** 包裹类型 id => 名称（[{id,name}]） */
function ba_parcel_types($opts = array())
{
    $c = ba_cache_get('parcel_types', 3600);
    if ($c !== null) {
        return array('ok' => true, 'data' => $c, 'error' => '', 'cached' => true);
    }
    $r = ba_get('/api/admin/meta/parceltypes', array(), $opts);
    if ($r['ok'] && is_array($r['data'])) {
        ba_cache_put('parcel_types', $r['data']);
    }
    return $r;
}

function ba_static_items($search = '', $limit = 300, $opts = array())
{
    $ck = 'static_items_' . md5($search . '|' . (int)$limit);
    $c  = ba_cache_get($ck, 1800);
    if ($c !== null) {
        return array('ok' => true, 'data' => $c, 'error' => '', 'cached' => true);
    }
    $r = ba_get('/api/admin/static/items', array('search' => $search, 'limit' => (int)$limit), $opts);
    if ($r['ok'] && is_array($r['data'])) {
        ba_cache_put($ck, $r['data']);
    }
    return $r;
}

function ba_static_characters($search = '', $limit = 500, $opts = array())
{
    $ck = 'static_chars_' . md5($search . '|' . (int)$limit);
    $c  = ba_cache_get($ck, 1800);
    if ($c !== null) {
        return array('ok' => true, 'data' => $c, 'error' => '', 'cached' => true);
    }
    $r = ba_get('/api/admin/static/characters', array('search' => $search, 'limit' => (int)$limit), $opts);
    if ($r['ok'] && is_array($r['data'])) {
        ba_cache_put($ck, $r['data']);
    }
    return $r;
}

/* ------------------------------------------------------------ 写入接口 --- */

/**
 * 发一封带附件的系统邮件。
 *
 * @param int    $serverId
 * @param string $sender
 * @param string $comment
 * @param array  $parcels  [['type'=>'Currency','id'=>4,'amount'=>1000], ...]
 * @param string $expireDate 'Y-m-d H:i:s' 或 '' 表示默认 7 天
 */
function ba_mail_send($serverId, $sender, $comment, $parcels, $expireDate = '')
{
    $body = array(
        'AccountServerId' => (int)$serverId,
        'Sender'          => (string)$sender,
        'Comment'         => (string)$comment,
        'Parcels'         => array_values($parcels),
    );
    if ($expireDate !== '' && $expireDate !== null) {
        $ts = strtotime($expireDate);
        if ($ts !== false) {
            $body['ExpireDate'] = date('c', $ts);
        }
    }
    return ba_post('/api/admin/mail/send', $body);
}

function ba_mail_delete($serverId, $mailServerId = 0, $clearAll = false)
{
    return ba_post('/api/admin/mail/delete', array(
        'AccountServerId' => (int)$serverId,
        'MailServerId'    => $mailServerId > 0 ? (int)$mailServerId : null,
        'ClearAll'        => (bool)$clearAll,
    ));
}

function ba_currency_set($serverId, $currencyType, $amount)
{
    return ba_post('/api/admin/currency/set', array(
        'AccountServerId' => (int)$serverId,
        'CurrencyType'    => (int)$currencyType,
        'Amount'          => (int)$amount,
    ));
}

function ba_account_update($serverId, $fields)
{
    $body = array('ServerId' => (int)$serverId);
    foreach (array('Nickname', 'CallName', 'Comment') as $k) {
        if (isset($fields[$k]) && $fields[$k] !== '') {
            $body[$k] = (string)$fields[$k];
        }
    }
    foreach (array('Level', 'Exp', 'VIPLevel', 'State') as $k) {
        if (isset($fields[$k]) && $fields[$k] !== '' && $fields[$k] !== null) {
            $body[$k] = (int)$fields[$k];
        }
    }
    return ba_post('/api/admin/account/update', $body);
}

function ba_item_give($serverId, $uniqueId, $amount, $setExact = false)
{
    return ba_post('/api/admin/items/give', array(
        'AccountServerId' => (int)$serverId,
        'UniqueId'        => (int)$uniqueId,
        'Amount'          => (int)$amount,
        'SetExact'        => (bool)$setExact,
    ));
}

function ba_item_remove($serverId, $uniqueId)
{
    return ba_post('/api/admin/items/remove', array(
        'AccountServerId' => (int)$serverId,
        'UniqueId'        => (int)$uniqueId,
    ));
}

function ba_command($uid, $command)
{
    return ba_post('/api/admin/command', array(
        'Uid'     => (int)$uid,
        'Command' => (string)$command,
    ), array('timeout' => 30));
}

function ba_account_create($nickname, $callName = '')
{
    return ba_post('/api/admin/account/create', array(
        'Nickname' => (string)$nickname,
        'CallName' => (string)$callName,
    ));
}

/* ------------------------------------------------------------ 小工具 --- */

/**
 * 把 /static/currencies 的 [{id,name}] 变成 id=>name 与 name=>id 两个映射。
 * 顺带硬编码几个关键 id 兜底（服务端不可达时下拉框仍然能用）。
 */
function ba_currency_maps()
{
    static $m = null;
    if ($m !== null) {
        return $m;
    }
    $id2name = array(
        1 => 'Gold', 2 => 'GemPaid', 3 => 'GemBonus', 4 => 'Gem', 5 => 'ActionPoint',
        6 => 'AcademyTicket', 7 => 'ArenaTicket', 8 => 'RaidTicket', 18 => 'MasterCoin',
        28 => 'CafeSummonTicket1', 29 => 'CafeSummonTicket2',
    );
    $r = ba_static_currencies();
    if ($r['ok'] && is_array($r['data'])) {
        foreach ($r['data'] as $row) {
            if (isset($row['id'], $row['name'])) {
                $id2name[(int)$row['id']] = (string)$row['name'];
            }
        }
    }
    $name2id = array();
    foreach ($id2name as $id => $name) {
        $name2id[$name] = $id;
    }
    $m = array('id2name' => $id2name, 'name2id' => $name2id);
    return $m;
}

/** 中文显示名（面板用），未收录的回落到英文名 */
function ba_currency_label($id, $name)
{
    static $cn = array(
        'Gold' => '金币', 'Gem' => '青辉石(合计)', 'GemBonus' => '青辉石(免费)', 'GemPaid' => '青辉石(付费)',
        'ActionPoint' => '体力', 'AcademyTicket' => '学院票', 'ArenaTicket' => '战术赛票', 'RaidTicket' => '总力战票',
        'MasterCoin' => '精通币', 'CafeSummonTicket1' => '咖啡厅召唤券1', 'CafeSummonTicket2' => '咖啡厅召唤券2',
        'WeekDungeonChaserATicket' => '周常A券', 'WeekDungeonChaserBTicket' => '周常B券',
        'WeekDungeonChaserCTicket' => '周常C券', 'WeekDungeonFindGiftTicket' => '寻宝券',
        'SchoolDungeonATicket' => '学院A券', 'SchoolDungeonBTicket' => '学院B券', 'SchoolDungeonCTicket' => '学院C券',
        'TimeAttackDungeonTicket' => '限时挑战券', 'WorldRaidTicketA' => '世界总力A券',
        'WorldRaidTicketB' => '世界总力B券', 'WorldRaidTicketC' => '世界总力C券',
        'ChaserTotalTicket' => '追猎合计券', 'SchoolDungeonTotalTicket' => '学院合计券',
        'EliminateTicketA' => '清剿A券', 'EliminateTicketB' => '清剿B券', 'EliminateTicketC' => '清剿C券',
        'EliminateTicketD' => '清剿D券',
    );
    $label = isset($cn[$name]) ? $cn[$name] : $name;
    return $label . '（#' . (int)$id . ' ' . $name . '）';
}

/** 面板里常用的包裹类型（发奖下拉框），Type 用枚举名 */
function ba_parcel_presets()
{
    return array(
        'Currency'     => '货币/青辉石/金币/体力',
        'Item'         => '道具',
        'Character'    => '角色',
        'Equipment'    => '装备',
        'MemoryLobby'  => '记忆大厅（L2D）',
        'FavorExp'     => '好感度经验',
        'AccountExp'   => '账号经验',
        'CharacterExp' => '角色经验',
        'GachaGroup'   => '招募券/卡池组',
        'Furniture'    => '家具',
    );
}

/** 健康检查：给仪表盘用的一行摘要 */
function ba_health()
{
    $r = ba_status();
    $out = array(
        'ok'      => (bool)$r['ok'],
        'error'   => (string)$r['error'],
        'ms'      => (int)$r['ms'],
        'name'    => '',
        'version' => '',
        'accounts' => 0,
        'uptime'  => 0,
        'base'    => ba_admin_base(),
    );
    if ($r['ok'] && is_array($r['data'])) {
        $out['name']     = isset($r['data']['service']) ? (string)$r['data']['service'] : 'Shittim-Server';
        $out['version']  = isset($r['data']['gameVersion']) ? (string)$r['data']['gameVersion'] : '';
        $out['accounts'] = isset($r['data']['accountCount']) ? (int)$r['data']['accountCount'] : 0;
        $out['uptime']   = isset($r['data']['uptimeSeconds']) ? (int)$r['data']['uptimeSeconds'] : 0;
    }
    return $out;
}
