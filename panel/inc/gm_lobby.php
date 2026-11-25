<?php
/**
 * inc/gm_lobby.php —— GM 面板「发放全部记忆大厅」
 *
 * 只做一件事：把「客户端认识的 258 个记忆大厅」切成 N 封系统邮件，逐封
 * POST /api/admin/mail/send。玩家在游戏里点领取时才真正入账（ParcelResolver）。
 *
 * ── 为什么 id 必须硬编码成这 258 个 ─────────────────────────────────────────
 * 大厅 id == 客户端 MemoryLobbyDBSchema.Id。服务端那份表是日服全量超集，
 * 发客户端不认识的 id 会让客户端渲染异常。所以这里只认客户端这 258 个，
 * 且做成常量：页面每次渲染零 IO，不读 ExcelDB.db、不查服务端。
 * 来源与校验见 plan/20261119/GM_LOBBY_IMPL.md。
 *
 * ── 幂等 ────────────────────────────────────────────────────────────────────
 * 服务端 ParcelResolver.UpdateMemoryLobby() 先按 (AccountServerId, MemoryLobbyUniqueId)
 * 查一次，已存在直接 return。所以重复点本按钮不会重复获得大厅，只会多几封邮件。
 *
 * ── Type 字段的两种写法（已实测）─────────────────────────────────────────────
 * 服务端 ParcelRequest.Type 是 string，AdminController 用 Enum.Parse<ParcelType>(p.Type)，
 * 因此 "MemoryLobby" 和 "8" 两种**字符串**都能解析成 ParcelType.MemoryLobby。
 * 但 JSON 里绝不能发裸数字 8：System.Text.Json 不把 number 反序列化进 string 字段。
 *
 * 2026-11-19 的线上实测（见 plan/20261119/GM_LOBBY_MAIL_CAPACITY.md）：
 *   "Type":"MemoryLobby"（字符串）→ HTTP 200，落库 Key.Type = 8
 *   "Type":8          （裸数字）  → HTTP 400
 *                              The JSON value could not be converted to System.String
 * 所以默认 'name'。'number' 模式发的是字符串 "8"（不是整数 8），保留作兜底；
 * 实测已经证明 'name' 可用，没有理由切过去。
 *
 * 顺带：那次实测也确认**一封邮件挂 258 个包裹是 200**（13 KB 请求体），
 * 甚至 1000 个也是 200。所以默认每封 60 个是纯保守值，不是接口限制；
 * 想一封发完就把 GM_MEMORY_LOBBY_PARCELS_PER_MAIL 改成 258（页面输入框也能直接填）。
 *
 * 约定：所有函数都不抛异常，失败返回数组由调用方展示。
 */

if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}

/* 客户端 MemoryLobbyDBSchema 的行数。运行时自检用，不等于这个数只记 WARN 不报错。 */
if (!defined('GM_MEMORY_LOBBY_EXPECTED_COUNT')) {
    define('GM_MEMORY_LOBBY_EXPECTED_COUNT', 258);
}
/* ParcelType.MemoryLobby 的枚举值（Schale/FlatData/ParcelType.cs:18 → 8）。 */
if (!defined('GM_MEMORY_LOBBY_PARCEL_TYPE_ID')) {
    define('GM_MEMORY_LOBBY_PARCEL_TYPE_ID', 8);
}
/* 每封邮件放多少个包裹的默认值。可随时改这里，或由页面表单覆盖。 */
if (!defined('GM_MEMORY_LOBBY_PARCELS_PER_MAIL')) {
    define('GM_MEMORY_LOBBY_PARCELS_PER_MAIL', 60);
}
/* 'name' → 发 "MemoryLobby"；'number' → 发字符串 "8"。 */
if (!defined('GM_MEMORY_LOBBY_TYPE_MODE')) {
    define('GM_MEMORY_LOBBY_TYPE_MODE', 'name');
}

/**
 * 客户端 MemoryLobbyDBSchema 的全部 id，共 258 个（升序，已去重）。
 *
 * 直接从 work/ba/data/ExcelDB.db 的 MemoryLobbyDBSchema 只读导出后硬编码，
 * 与 srv_src/Shittim-Server/Resources/ClientMemoryLobbyIds.txt 逐行一致。
 * 分段：10000-10098(99) 10100-10136(37) 13000-13014(15) 16000-16019(20)
 *       20000-20056(57) 23000-23008(9) 26000-26015(16) + 5 个 7 位 id = 258
 *
 * @return int[]
 */
function gm_memory_lobby_ids()
{
    static $ids = null;
    if ($ids !== null) {
        return $ids;
    }

    $ids = array(
        /* 10000 – 10098 · 99 个 */
        10000, 10001, 10002, 10003, 10004, 10005, 10006, 10007, 10008, 10009,
        10010, 10011, 10012, 10013, 10014, 10015, 10016, 10017, 10018, 10019,
        10020, 10021, 10022, 10023, 10024, 10025, 10026, 10027, 10028, 10029,
        10030, 10031, 10032, 10033, 10034, 10035, 10036, 10037, 10038, 10039,
        10040, 10041, 10042, 10043, 10044, 10045, 10046, 10047, 10048, 10049,
        10050, 10051, 10052, 10053, 10054, 10055, 10056, 10057, 10058, 10059,
        10060, 10061, 10062, 10063, 10064, 10065, 10066, 10067, 10068, 10069,
        10070, 10071, 10072, 10073, 10074, 10075, 10076, 10077, 10078, 10079,
        10080, 10081, 10082, 10083, 10084, 10085, 10086, 10087, 10088, 10089,
        10090, 10091, 10092, 10093, 10094, 10095, 10096, 10097, 10098,
        /* 10100 – 10136 · 37 个 */
        10100, 10101, 10102, 10103, 10104, 10105, 10106, 10107, 10108, 10109,
        10110, 10111, 10112, 10113, 10114, 10115, 10116, 10117, 10118, 10119,
        10120, 10121, 10122, 10123, 10124, 10125, 10126, 10127, 10128, 10129,
        10130, 10131, 10132, 10133, 10134, 10135, 10136,
        /* 13000 – 13014 · 15 个 */
        13000, 13001, 13002, 13003, 13004, 13005, 13006, 13007, 13008, 13009,
        13010, 13011, 13012, 13013, 13014,
        /* 16000 – 16019 · 20 个 */
        16000, 16001, 16002, 16003, 16004, 16005, 16006, 16007, 16008, 16009,
        16010, 16011, 16012, 16013, 16014, 16015, 16016, 16017, 16018, 16019,
        /* 20000 – 20056 · 57 个 */
        20000, 20001, 20002, 20003, 20004, 20005, 20006, 20007, 20008, 20009,
        20010, 20011, 20012, 20013, 20014, 20015, 20016, 20017, 20018, 20019,
        20020, 20021, 20022, 20023, 20024, 20025, 20026, 20027, 20028, 20029,
        20030, 20031, 20032, 20033, 20034, 20035, 20036, 20037, 20038, 20039,
        20040, 20041, 20042, 20043, 20044, 20045, 20046, 20047, 20048, 20049,
        20050, 20051, 20052, 20053, 20054, 20055, 20056,
        /* 23000 – 23008 · 9 个 */
        23000, 23001, 23002, 23003, 23004, 23005, 23006, 23007, 23008,
        /* 26000 – 26015 · 16 个 */
        26000, 26001, 26002, 26003, 26004, 26005, 26006, 26007, 26008, 26009,
        26010, 26011, 26012, 26013, 26014, 26015,
        /* 7 位 id · 5 个 */
        1000501, 1001001, 1300401, 1300801, 2300501,
    );

    return $ids;
}

/**
 * 运行时自检：数量是否为 258、是否有重复。
 *
 * 数量不符只记 WARN，**以实际数组为准继续发**（不报错、不拦截）。
 * 传 $ids / $expected 可注入测试数据；不传时结果按请求缓存。
 *
 * @param  int[]|null $ids
 * @param  int|null   $expected
 * @return array ['ok'=>bool,'expected'=>int,'actual'=>int,'unique'=>int,'warn'=>string]
 */
function gm_memory_lobby_selfcheck($ids = null, $expected = null)
{
    static $cache = null;
    $useDefault = ($ids === null && $expected === null);
    if ($useDefault && $cache !== null) {
        return $cache;
    }

    if ($ids === null) {
        $ids = gm_memory_lobby_ids();
    }
    if ($expected === null) {
        $expected = GM_MEMORY_LOBBY_EXPECTED_COUNT;
    }

    $all    = array_values($ids);
    $actual = count($all);
    $unique = count(array_unique(array_map('intval', $all)));
    $warns  = array();

    if ($actual !== (int)$expected) {
        $warns[] = '记忆大厅 id 数量异常：期望 ' . (int)$expected . ' 个，实际 ' . $actual
                 . ' 个（以实际数组为准，操作继续）';
    }
    if ($unique !== $actual) {
        $warns[] = '记忆大厅 id 有重复：' . $actual . ' 条里只有 ' . $unique . ' 个不同值';
    }
    foreach ($all as $v) {
        if ((int)$v <= 0) {
            $warns[] = '记忆大厅 id 出现非法值：' . var_export($v, true);
            break;
        }
    }

    $warn = implode('；', $warns);
    if ($warn !== '') {
        error_log('[gm_lobby] WARN ' . $warn);
    }

    $res = array(
        'ok'       => ($warn === ''),
        'expected' => (int)$expected,
        'actual'   => $actual,
        'unique'   => $unique,
        'warn'     => $warn,
    );
    if ($useDefault) {
        $cache = $res;
    }
    return $res;
}

/** 'name' | 'number'（小写，非法值回落 'name'） */
function gm_memory_lobby_type_mode()
{
    $m = strtolower(trim((string)GM_MEMORY_LOBBY_TYPE_MODE));
    return ($m === 'number') ? 'number' : 'name';
}

/**
 * 写进 parcel.Type 的值：字符串。
 * 'name' → 'MemoryLobby'；'number' → '8'（**字符串**，不是整数）。
 */
function gm_memory_lobby_type_value()
{
    return (gm_memory_lobby_type_mode() === 'number')
        ? (string)GM_MEMORY_LOBBY_PARCEL_TYPE_ID
        : 'MemoryLobby';
}

/** 默认每封包裹数（来自常量 GM_MEMORY_LOBBY_PARCELS_PER_MAIL，非法值回落 60） */
function gm_memory_lobby_default_per_mail()
{
    $n = (int)GM_MEMORY_LOBBY_PARCELS_PER_MAIL;
    return ($n < 1) ? 60 : $n;
}

/** 把每封包裹数夹到 1..总数；非法值回落默认 60 */
function gm_memory_lobby_clamp_per_mail($n, $total = null)
{
    if ($total === null) {
        $total = count(gm_memory_lobby_ids());
    }
    $total   = max(1, (int)$total);
    $default = gm_memory_lobby_default_per_mail();

    $n = (int)$n;
    if ($n < 1) {
        $n = $default;
    }
    if ($n > $total) {
        $n = $total;
    }
    return $n;
}

/**
 * 按 $perMail 把 id 切成 N 份（顺序不变，不留空份）。
 *
 * @param  int[] $ids
 * @param  int   $perMail
 * @return array<int, int[]>
 */
function gm_memory_lobby_slice($ids, $perMail)
{
    $list = array_values(array_map('intval', (array)$ids));
    $n    = count($list);
    if ($n === 0) {
        return array();
    }
    $perMail = gm_memory_lobby_clamp_per_mail($perMail, $n);

    $out = array();
    for ($i = 0; $i < $n; $i += $perMail) {
        $out[] = array_slice($list, $i, $perMail);
    }
    return $out;
}

/**
 * 发送计划（页面显示「本次将分 X 封邮件发送」用，不发请求）。
 *
 * @return array ['perMail'=>int,'mails'=>int,'parcels'=>int,'sizes'=>int[],'slices'=>array]
 */
function gm_memory_lobby_plan($ids = null, $perMail = null)
{
    if ($ids === null) {
        $ids = gm_memory_lobby_ids();
    }
    if ($perMail === null) {
        $perMail = GM_MEMORY_LOBBY_PARCELS_PER_MAIL;
    }
    $list   = array_values(array_map('intval', (array)$ids));
    $perMail = gm_memory_lobby_clamp_per_mail($perMail, count($list));
    $slices = gm_memory_lobby_slice($list, $perMail);

    $sizes = array();
    foreach ($slices as $s) {
        $sizes[] = count($s);
    }

    return array(
        'perMail' => $perMail,
        'mails'   => count($slices),
        'parcels' => count($list),
        'sizes'   => $sizes,
        'slices'  => $slices,
    );
}

/**
 * 给一个账号发放全部记忆大厅：切成 N 封邮件逐封发送。
 *
 * 单封失败不影响后续（继续发下一封），所有错误收集进 'errors'。
 * 只要有一封失败，'ok' 就是 false —— 调用方据此标记该玩家失败，
 * 但已成功的那些邮件已经进邮箱，重跑一遍是安全的（幂等）。
 *
 * @param  int        $accountServerId
 * @param  int|null   $parcelsPerMail  每封包裹数，null/非法 → 默认 60
 * @param  int[]|null $ids             默认用客户端那 258 个
 * @param  array      $opts            ['sender'=>string, 'sender'=>callable]
 *                                     'sender' 为 callable 时用它替代 ba_post，
 *                                     签名 fn($uid, $sender, $comment, $parcels, $no, $total): array
 * @return array ['ok'=>bool,'mails'=>int,'parcels'=>int,'errors'=>string[],
 *                'ok_mails'=>int,'fail_mails'=>int,'account'=>int,'per_mail'=>int,
 *                'type'=>string,'sender'=>string]
 */
function gm_grant_memory_lobbies($accountServerId, $parcelsPerMail = null, $ids = null, $opts = array())
{
    $uid   = (int)$accountServerId;
    $plan  = gm_memory_lobby_plan($ids, $parcelsPerMail);
    $type  = gm_memory_lobby_type_value();
    $senderName = isset($opts['sender_name']) ? (string)$opts['sender_name'] : 'Schale';
    if ($senderName === '') {
        $senderName = 'Schale';
    }
    $senderFn = (isset($opts['sender']) && is_callable($opts['sender'])) ? $opts['sender'] : null;

    $res = array(
        'ok'         => false,
        'mails'      => (int)$plan['mails'],
        'parcels'    => (int)$plan['parcels'],
        'errors'     => array(),
        'ok_mails'   => 0,
        'fail_mails' => 0,
        'account'    => $uid,
        'per_mail'   => (int)$plan['perMail'],
        'type'       => $type,
        'sender'     => $senderName,
    );

    if ($uid <= 0) {
        $res['errors'][] = 'AccountServerId 无效：' . $uid;
        return $res;
    }
    if (!$plan['slices']) {
        $res['errors'][] = '没有任何记忆大厅 id 可发放';
        return $res;
    }

    $total = (int)$plan['mails'];
    foreach ($plan['slices'] as $i => $slice) {
        $no = $i + 1;

        $parcels = array();
        foreach ($slice as $lid) {
            /* Amount 必须 ≥1：服务端按 parcel.Amount 建 ParcelInfo，0 会让附件显示为空。 */
            $parcels[] = array('Type' => $type, 'Id' => (int)$lid, 'Amount' => 1);
        }
        $comment = '记忆大厅全部解锁（' . $no . '/' . $total . '）';

        if ($senderFn !== null) {
            $r = call_user_func($senderFn, $uid, $senderName, $comment, $parcels, $no, $total);
        } elseif (function_exists('ba_post')) {
            $r = ba_post('/api/admin/mail/send', array(
                'AccountServerId' => $uid,
                'Sender'          => $senderName,
                'Comment'         => $comment,
                'Parcels'         => $parcels,
            ));
        } else {
            $r = array('ok' => false, 'status' => 0, 'error' => 'inc/ba.php 未加载（ba_post 不存在）');
        }

        if (is_array($r) && !empty($r['ok'])) {
            $res['ok_mails']++;
            continue;
        }

        /* ── 这一封失败：记下来，继续下一封 ── */
        $res['fail_mails']++;
        $err    = (is_array($r) && isset($r['error']) && (string)$r['error'] !== '')
            ? (string)$r['error']
            : '未知错误';
        $status = (is_array($r) && isset($r['status'])) ? (int)$r['status'] : 0;
        if ($status > 0) {
            $err .= '（HTTP ' . $status . '）';
        }
        $res['errors'][] = '第 ' . $no . '/' . $total . ' 封（' . count($slice)
            . ' 个包裹，Id ' . $slice[0] . '–' . $slice[count($slice) - 1] . '）失败：' . $err;
    }

    $res['ok'] = ($res['fail_mails'] === 0 && $res['ok_mails'] > 0);
    return $res;
}

/**
 * 批量版：对每个账号各调一次 gm_grant_memory_lobbies()。
 *
 * 页面「选中玩家 / 全服」两条路都走这里；accountIds 里有几个账号就调几次，
 * 某个账号失败不影响后面的账号。
 *
 * @param  int[]      $accountIds
 * @param  int|null   $parcelsPerMail
 * @param  int[]|null $ids
 * @param  array      $opts
 * @return array<int, array> 与 $accountIds 同序的结果数组（键被重置为 0..n-1）
 */
function gm_grant_memory_lobbies_batch($accountIds, $parcelsPerMail = null, $ids = null, $opts = array())
{
    $out = array();
    foreach ((array)$accountIds as $sid) {
        $out[] = gm_grant_memory_lobbies((int)$sid, $parcelsPerMail, $ids, $opts);
    }
    return $out;
}
