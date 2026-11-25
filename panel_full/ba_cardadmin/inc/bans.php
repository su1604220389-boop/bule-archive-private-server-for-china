<?php
/**
 * bans_inc.php —— 封禁域：账号 / 卡密 / 设备（三个**正交**维度）+ 限时封禁
 *
 * 部署名：`/www/wwwroot/ba_cardadmin/inc/bans.php`（本文件就是它的完整源码）
 *
 * 维度         写到哪里                                     封            解
 * ----------   ------------------------------------------   -----------   -----------
 * 账号封禁     Shittim `Accounts.State`                     2=Dormant     1=Normal
 * 卡密封禁     MySQL `cards.status`                         disabled      active
 * 设备封禁     SDK 黑名单文件（一行一个设备号）             追加该行      删除该行
 *
 * 【本版新增 · 第五节】限时封禁表 `bans`（桥接库 accounts.db，kind = account|card|device）：
 *   · 每个维度都支持 永久 / 1 小时 / 1 天 / 7 天 / 30 天 / 自定义时间点；
 *   · until_epoch IS NULL = 永久；until_epoch <= now = 已到期（**读取侧**判定，不靠定时任务）；
 *   · 文案统一函数 ban_msg()：永久 "封禁，请联系客服"，
 *     限时 "封号时间 2026-11-18 20:00 至 2026-11-20 20:00，请联系客服"；
 *     由 SDK（ban_message.py）原样下发到客户端弹窗。
 *   · "永久"才写旧机制（State / cards.status / device_ban.txt）做双保险；
 *     "限时"只写新表，到期自动恢复，不需要任何人工/定时清理（理由见 CHECK.md §2.4）。
 *
 * 三条链路彼此独立：本文件里没有任何「顺手带上另一个维度」的逻辑，页面也是三个独立按钮。
 * 要三个一起封/解，只能在页面上显式点「全封 / 全解」（带二次确认）。
 *
 * 约定：所有函数都不抛异常；失败返回 array('ok' => false, 'error' => '人话')。
 * 依赖：只用 inc/db.php / inc/ba.php / inc/players.php / inc/helpers.php 里**已有**的函数，
 *       不新增 helpers 函数，也不改 inc/players.php、inc/ba.php、inc/sync.php。
 */

if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}

require_once __DIR__ . '/db.php';
require_once __DIR__ . '/ba.php';
require_once __DIR__ . '/players.php';

/* ============================================================================
 * 一、设备黑名单文件（SDK 侧）
 *
 * SDK 补丁（另一个补丁实现）在 /user/login、/user/quick-login、/user/detail
 * 命中文件里的设备号就返回 {"Code":400101,"Msg":"设备已被限制","Data":{}}。
 * 文件格式：一行一个设备号；空行与 # 开头的行忽略。
 * 读-改-写全程 flock 排它锁；落盘用「临时文件 + rename」原子替换，
 * 保证 SDK 任何时刻读到的都是完整文件。
 * ========================================================================== */

/**
 * 设备黑名单文件路径。
 * 优先级：常量 BA_DEVICE_BAN_FILE > settings.ba_device_ban_file > 默认路径。
 * @return string
 */
function ban_device_file_path()
{
    static $path = null;
    if ($path !== null) {
        return $path;
    }
    $path = '';
    if (defined('BA_DEVICE_BAN_FILE') && (string)BA_DEVICE_BAN_FILE !== '') {
        $path = (string)BA_DEVICE_BAN_FILE;
    }
    if ($path === '' && function_exists('setting_get')) {
        try {
            $path = trim((string)setting_get('ba_device_ban_file', ''));
        } catch (Throwable $e) {
            $path = '';
        }
    }
    if ($path === '') {
        $path = '/www/wwwroot/ba_sdk/device_ban.txt';
    }
    return $path;
}

/** 锁文件路径（与被改写的目标文件分开，避免 rename 换掉 inode 导致锁失效） */
function ban_device_lock_path()
{
    return ban_device_file_path() . '.lock';
}

/**
 * 黑名单文件/目录的健康状态（给页面顶部信息条用，只读）
 * @return array
 */
function ban_device_file_status()
{
    $path = ban_device_file_path();
    $dir  = dirname($path);
    $st = array(
        'path'         => $path,
        'dir'          => $dir,
        'lock'         => ban_device_lock_path(),
        'exists'       => is_file($path),
        'readable'     => is_readable($path),
        'writable'     => is_file($path) ? is_writable($path) : false,
        'dir_writable' => is_dir($dir) ? is_writable($dir) : false,
        'bytes'        => 0,
        'mtime'        => 0,
        'count'        => 0,
        'error'        => '',
    );
    if ($st['exists']) {
        $st['bytes'] = (int)@filesize($path);
        $st['mtime'] = (int)@filemtime($path);
    }
    $st['count'] = count(ban_device_list(true));

    if (!$st['dir_writable'] && !$st['writable']) {
        $st['error'] = 'PHP 进程对 ' . $dir . ' 没有写权限，设备封禁会失败。'
            . '请执行：chown -R www:www ' . $dir . '（或 chmod 775 该目录）。';
    } elseif ($st['exists'] && !$st['readable']) {
        $st['error'] = '黑名单文件存在但不可读：' . $path;
    }
    return $st;
}

/**
 * 把黑名单文本拆成「原始行 + 有效设备行（行号 => 设备号）」
 * @param string $text
 * @return array('lines'=>array,'devices'=>array)
 */
function ban_device_parse($text)
{
    $text  = str_replace(array("\r\n", "\r"), "\n", (string)$text);
    $lines = ($text === '') ? array() : explode("\n", $text);
    $devices = array();
    foreach ($lines as $i => $line) {
        $t = trim($line);
        if ($t === '' || $t[0] === '#') {
            continue;
        }
        $devices[$i] = $t;
    }
    return array('lines' => $lines, 'devices' => $devices);
}

/**
 * 当前黑名单里的设备号（去重、保序）
 * @param bool $reload 丢掉静态缓存重新读盘
 * @return array 设备号字符串数组
 */
function ban_device_list($reload = false)
{
    static $list = null;
    if ($list !== null && !$reload) {
        return $list;
    }
    $list = array();
    $path = ban_device_file_path();
    if (!is_file($path) || !is_readable($path)) {
        return $list;
    }
    $raw = @file_get_contents($path);
    if ($raw === false) {
        return $list;
    }
    $parsed = ban_device_parse($raw);
    $seen   = array();
    foreach ($parsed['devices'] as $dev) {
        if (isset($seen[$dev])) {
            continue;
        }
        $seen[$dev] = true;
        $list[]     = $dev;
    }
    return $list;
}

/**
 * 某个设备号是否已在黑名单里（精确匹配，区分大小写）
 * @param string $dev
 * @return bool
 */
function ban_device_has($dev)
{
    $dev = trim((string)$dev);
    if ($dev === '') {
        return false;
    }
    return in_array($dev, ban_device_list(), true);
}

/**
 * 原子写：临时文件 + rename（同目录，跨盘 rename 会失败所以必须同目录）
 * @param string $path
 * @param string $content
 * @return string 空串 = 成功；否则是给用户看的中文错误
 */
function ban_device_atomic_write($path, $content)
{
    $dir = dirname($path);
    if (!is_dir($dir) && (!function_exists('ensure_dir') || !@ensure_dir($dir))) {
        return '目录不存在且无法创建：' . $dir;
    }
    $pid = function_exists('getmypid') ? (int)getmypid() : 0;
    $tmp = $path . '.tmp.' . $pid . '.' . substr(md5(uniqid('', true)), 0, 6);
    $fp  = @fopen($tmp, 'wb');
    if ($fp === false) {
        return '无法创建临时文件：' . $tmp . '（检查 ' . $dir . ' 的写权限，必要时 chown -R www:www ' . $dir . '）';
    }
    $len = strlen($content);
    $ok  = true;
    if ($len > 0) {
        $w = @fwrite($fp, $content);
        if ($w === false || $w < $len) {
            $ok = false;
        }
    }
    if ($ok) {
        @fflush($fp);
    }
    @fclose($fp);
    if (!$ok) {
        @unlink($tmp);
        return '写入临时文件失败：' . $tmp;
    }
    @chmod($tmp, 0644);
    if (!@rename($tmp, $path)) {
        /* 少数环境（跨文件系统）rename 会失败：退化成 copy + unlink，仍在锁保护内 */
        $copied = @copy($tmp, $path);
        @unlink($tmp);
        if (!$copied) {
            return '替换目标文件失败：' . $path;
        }
        @chmod($path, 0644);
    }
    return '';
}

/**
 * 封禁 / 解封一个设备（读-改-写，全程 flock 排它锁）
 *
 * @param string $dev 设备号
 * @param bool   $on  true=写入黑名单，false=从黑名单删除
 * @return array('ok'=>bool,'error'=>string,'changed'=>bool,'count'=>int,'path'=>string,'device'=>string)
 */
function ban_device_set($dev, $on)
{
    $dev = trim((string)$dev);
    $out = array(
        'ok' => false, 'error' => '', 'changed' => false,
        'count' => 0, 'path' => ban_device_file_path(), 'device' => $dev,
    );
    if ($dev === '') {
        $out['error'] = '设备号为空';
        return $out;
    }
    if (strlen($dev) > 128) {
        $out['error'] = '设备号过长（超过 128 字节），拒绝写入';
        return $out;
    }
    if (preg_match('/[\r\n\t]/', $dev) !== 0 || $dev[0] === '#') {
        $out['error'] = '设备号里不能有换行/制表符，也不能以 # 开头（会被当成注释）';
        return $out;
    }

    $path = ban_device_file_path();
    $dir  = dirname($path);
    if (!is_dir($dir) && (!function_exists('ensure_dir') || !@ensure_dir($dir))) {
        $out['error'] = '黑名单目录不存在且无法创建：' . $dir;
        return $out;
    }

    $lock = ban_device_lock_path();
    $fp   = @fopen($lock, 'c');
    if ($fp === false) {
        $out['error'] = '无法打开锁文件：' . $lock . '（检查该目录写权限）';
        return $out;
    }
    @chmod($lock, 0666);

    /* 拿锁：最多等约 1 秒（20 × 50ms），拿不到就报错，绝不把 web 请求挂死 */
    $locked = false;
    for ($i = 0; $i < 20; $i++) {
        if (@flock($fp, LOCK_EX | LOCK_NB)) {
            $locked = true;
            break;
        }
        @usleep(50000);
    }
    if (!$locked) {
        @fclose($fp);
        $out['error'] = '另一个进程正在写黑名单文件，请稍后重试';
        return $out;
    }

    try {
        if (is_file($path) && !is_readable($path)) {
            $out['error'] = '黑名单文件存在但不可读：' . $path;
            return $out;
        }
        $raw = is_file($path) ? @file_get_contents($path) : '';
        if ($raw === false) {
            $out['error'] = '读取黑名单文件失败：' . $path;
            return $out;
        }

        $parsed = ban_device_parse($raw);
        $lines  = $parsed['lines'];
        /* 末尾因换行产生的空行先去掉，重组时统一补一个 \n */
        while (count($lines) > 0 && trim((string)end($lines)) === '') {
            array_pop($lines);
        }

        $found = -1;
        foreach ($parsed['devices'] as $idx => $d) {
            if ($d === $dev) {
                $found = $idx;
                break;
            }
        }

        $want = (bool)$on;
        $have = ($found >= 0);

        if ($want === $have) {
            $out['ok']      = true;
            $out['changed'] = false;
            $out['count']   = count(ban_device_list(true));
            return $out;
        }

        if ($want) {
            $lines[] = $dev;
        } else {
            $kept = array();
            foreach ($lines as $i => $line) {
                if (isset($parsed['devices'][$i]) && $parsed['devices'][$i] === $dev) {
                    continue;   /* 删掉这一行（重复行也一起删） */
                }
                $kept[] = $line;
            }
            $lines = $kept;
        }

        $content = (count($lines) > 0) ? (implode("\n", $lines) . "\n") : '';
        $wr = ban_device_atomic_write($path, $content);
        if ($wr !== '') {
            $out['error'] = $wr;
            return $out;
        }

        $out['ok']      = true;
        $out['changed'] = true;
        $out['count']   = count(ban_device_list(true));
        return $out;
    } catch (Throwable $e) {
        $out['error'] = '写黑名单文件异常：' . $e->getMessage();
        return $out;
    } finally {
        @flock($fp, LOCK_UN);
        @fclose($fp);
    }
}

/**
 * cards.json 路径（与 cron/sync 用的是同一个 settings 键；读不到就回落常量）
 * 注意：这里只读文件做「设备候选」，不调用 inc/sync.php 的任何函数。
 */
function ban_cards_json_path()
{
    static $path = null;
    if ($path !== null) {
        return $path;
    }
    $path = '';
    if (function_exists('setting_get')) {
        try {
            $path = trim((string)setting_get('cards_json_path', ''));
        } catch (Throwable $e) {
            $path = '';
        }
    }
    if ($path === '') {
        $path = defined('CARDS_JSON_PATH') ? (string)CARDS_JSON_PATH : '/root/bapatch/cards.json';
    }
    return $path;
}

/**
 * 往设备候选表里合并一条（内部用；$devs 以设备号为键）
 * @param array  $devs   设备号 => array(device, sources[], cards[], accounts[], banned)
 * @param string $dev
 * @param string $source 来源标签
 * @param string $cardKey 关联卡密（可为空）
 * @param array|null $account array('server_id','nickname','publisher_id')
 */
function ban_device_cand_add(&$devs, $dev, $source, $cardKey = '', $account = null)
{
    $dev = trim((string)$dev);
    if ($dev === '' || strlen($dev) > 128) {
        return;
    }
    if ($dev[0] === '#' || preg_match('/[\r\n\t]/', $dev) !== 0) {
        return;
    }
    if (!isset($devs[$dev])) {
        $devs[$dev] = array(
            'device'   => $dev,
            'sources'  => array(),
            'cards'    => array(),
            'accounts' => array(),
            'banned'   => false,
        );
    }
    if ($source !== '' && !in_array($source, $devs[$dev]['sources'], true)) {
        $devs[$dev]['sources'][] = $source;
    }
    if ($cardKey !== '' && !in_array($cardKey, $devs[$dev]['cards'], true)) {
        $devs[$dev]['cards'][] = $cardKey;
    }
    if (is_array($account) && isset($account['server_id'])) {
        $sid = (int)$account['server_id'];
        if ($sid > 0 && !isset($devs[$dev]['accounts'][$sid])) {
            $devs[$dev]['accounts'][$sid] = array(
                'server_id'    => $sid,
                'nickname'     => isset($account['nickname']) ? (string)$account['nickname'] : '',
                'publisher_id' => isset($account['publisher_id']) ? (int)$account['publisher_id'] : 0,
                'source'       => $source,
            );
        }
    }
}

/**
 * 可封禁的设备候选：设备号 + 它绑定过哪些卡/账号。
 *
 * 三路来源（能拿到几路就聚合几路，缺的那路只记 warning，不抛异常）：
 *   1. accounts.db（桥接账号镜像，只读）：accounts.device_unique_id、accounts.dev_id
 *   2. cards.json（SDK 侧卡密库，只读）：cards[*].devices
 *   3. MySQL card_devices：面板自己记的设备绑定
 *
 * @param bool $reload
 * @return array('ok'=>bool,'error'=>string,'devices'=>array,'warnings'=>array,'sources'=>array,'count'=>int)
 */
function ban_device_candidates($reload = false)
{
    static $cache = null;
    if ($cache !== null && !$reload) {
        return $cache;
    }

    $out = array(
        'ok'       => true,
        'error'    => '',
        'devices'  => array(),
        'warnings' => array(),
        'count'    => 0,
        'sources'  => array(
            'accounts_db'     => false,
            'cards_json'      => false,
            'card_devices'    => 0,
            'accounts_db_path' => function_exists('player_accounts_db_path') ? player_accounts_db_path() : '',
            'cards_json_path' => ban_cards_json_path(),
        ),
    );

    $devs = array();

    /* --- ① accounts.db（桥接镜像） ------------------------------------- */
    $bridge = function_exists('player_bridge_accounts') ? player_bridge_accounts() : array();
    if ($bridge) {
        $out['sources']['accounts_db'] = true;
        $n = 0;
        foreach ($bridge as $pub => $row) {
            $n++;
            if ($n > 20000) {
                $out['warnings'][] = 'accounts.db 行数过多，只聚合了前 20000 行';
                break;
            }
            $sid = isset($row['shittim_server_id']) ? (int)$row['shittim_server_id'] : 0;
            if ($sid <= 0 && isset($row['server_id'])) {
                $sid = (int)$row['server_id'];   /* 老库没回写 shittim_server_id 时退回桥接侧 id */
            }
            $acc = array(
                'server_id'    => $sid,
                'nickname'     => isset($row['nickname']) ? (string)$row['nickname'] : '',
                'publisher_id' => (int)$pub,
            );
            /* [DEVFIX2 2026-11-18] 这里原来还把 accounts.db.device_unique_id 当设备号加进候选。
             * 那是**桥自己算的 32 位串**，没有任何一层拿它做拦截：
             *   · 桥只判 bans.kind='account'（不判 device）
             *   · SDK 只判 device_ban.txt 里的 **16 位 DeviceID**（客户端的 Authorization.Head.DeviceID）
             * 封了不生效 = 假按钮，所以去掉。真设备号只从 cards.json / card_devices 来。
             * 原代码（留档）：
             *   if (isset($row['device_unique_id'])) {
             *       ban_device_cand_add($devs, (string)$row['device_unique_id'], 'accounts.db.device_unique_id', '', $acc);
             *   }
             */
            /* [DEVFIX 2026-11-18] 这里原来还有一段把 $row['dev_id'] 当设备号加进候选，
             * 但 accounts.db.dev_id 与 publisher_account_id **恒等**（9 位数字），
             * 它是账号身份、不是设备号。加进去的后果：设备封禁是整串精确匹配，
             * 管理员点"封这个设备"写出的 bans(kind='device', target='819675745')
             * 永远匹配不到任何真机 —— 看着封了、实际没封。
             * 真设备只有两路：accounts.db.device_unique_id（桥）和 SDK 的 DeviceID（cards.json / card_devices）。
             * 原代码（留档）：
             *   if (isset($row['dev_id'])) {
             *       ban_device_cand_add($devs, (string)$row['dev_id'], 'accounts.db.dev_id', '', $acc);
             *   }
             */
        }
    } else {
        $err = '';
        if (function_exists('player_bridge_status')) {
            $bs  = player_bridge_status();
            $err = isset($bs['error']) ? (string)$bs['error'] : '';
        }
        $out['warnings'][] = '桥接账号库不可用'
            . (function_exists('player_accounts_db_path') ? ('（' . player_accounts_db_path() . '）') : '')
            . ($err !== '' ? ('：' . $err) : '')
            . '；accounts.db 这一路设备候选已跳过。';
    }

    /* --- ② cards.json -------------------------------------------------- */
    $jsonPath = ban_cards_json_path();
    if (is_file($jsonPath) && is_readable($jsonPath)) {
        $raw = @file_get_contents($jsonPath);
        if ($raw === false) {
            $out['warnings'][] = 'cards.json 读取失败：' . $jsonPath;
        } else {
            $j = json_decode($raw, true);
            if (!is_array($j) || !isset($j['cards']) || !is_array($j['cards'])) {
                $out['warnings'][] = 'cards.json 不是可解析的卡密库（json_decode 失败），已跳过这一路：' . $jsonPath;
            } else {
                $out['sources']['cards_json'] = true;
                foreach ($j['cards'] as $key => $rec) {
                    if (!is_array($rec) || !isset($rec['devices']) || !is_array($rec['devices'])) {
                        continue;
                    }
                    foreach ($rec['devices'] as $d) {
                        if (!is_string($d)) {
                            continue;
                        }
                        ban_device_cand_add($devs, $d, 'cards.json', (string)$key, null);
                    }
                }
            }
        }
    } else {
        $out['warnings'][] = 'cards.json 不在或不可读：' . $jsonPath . '（cards.json 这一路设备候选已跳过）';
    }

    /* --- ③ MySQL card_devices ------------------------------------------ */
    try {
        $rows = db_all('SELECT d.device_id AS device_id, c.card_key AS card_key
                          FROM card_devices d
                          LEFT JOIN cards c ON c.id = d.card_id');
        $out['sources']['card_devices'] = count($rows);
        foreach ($rows as $r) {
            ban_device_cand_add($devs, (string)$r['device_id'], 'mysql.card_devices',
                isset($r['card_key']) ? (string)$r['card_key'] : '', null);
        }
    } catch (Throwable $e) {
        $out['warnings'][] = 'MySQL card_devices 读取失败：' . $e->getMessage();
    }

    /* --- 已封禁标记 + 文件里有但三路都没见过的设备 --------------------- */
    $banSet = array();
    foreach (ban_device_list() as $d) {
        $banSet[$d] = true;
    }
    foreach ($banSet as $d => $x) {
        if (!isset($devs[$d])) {
            ban_device_cand_add($devs, $d, 'device_ban.txt', '', null);
        }
    }
    foreach ($devs as $d => $info) {
        $devs[$d]['banned'] = isset($banSet[$d]);
    }

    ksort($devs);
    $out['devices'] = $devs;
    $out['count']   = count($devs);

    $cache = $out;
    return $out;
}

/* ============================================================================
 * 二、卡密封禁（MySQL cards.status）
 * ========================================================================== */

/**
 * 禁用 / 启用一张卡密。
 * 成功后在 notice 里带上「≤60 秒同步到 cards.json，或去仪表盘点立即同步」的提示。
 *
 * [GATEFIX] 这里同时是「卡密封禁 -> 账号封禁行」的入口：状态改成功以后会顺手把这张卡的
 * publisher 映射成一条 bans(kind='account') 行（桥只认这个维度，才能弹官方封禁框）。
 * 映射失败**不影响**卡密状态（失败方向 = 放行，不会误封），但一定会写进
 * notice / warnings + 审计，运营看得见（见 NOTES.md §4）。
 *
 * @param int  $cardId
 * @param bool $on true=禁用（disabled），false=启用（active）
 * @return array('ok'=>bool,'error'=>string,'notice'=>string,'warnings'=>array,'bancard'=>array,
 *               'card_id'=>int,'card_key'=>string,'old_status'=>string,'new_status'=>string)
 */
function ban_card_toggle($cardId, $on)
{
    $cardId = (int)$cardId;
    $new    = $on ? 'disabled' : 'active';
    $out = array(
        'ok' => false, 'error' => '', 'notice' => '', 'warnings' => array(), 'bancard' => array(),
        'card_id' => $cardId, 'card_key' => '', 'old_status' => '', 'new_status' => $new,
    );
    if ($cardId <= 0) {
        $out['error'] = '卡密 id 无效';
        return $out;
    }

    $row = null;
    try {
        $row = db_row('SELECT `id`, `card_key`, `status` FROM `cards` WHERE `id` = ? LIMIT 1', array($cardId));
    } catch (Throwable $e) {
        $out['error'] = '数据库不可用：' . $e->getMessage();
        return $out;
    }
    if (!$row) {
        $out['error'] = '找不到卡密 #' . $cardId . '（可能已被删除）';
        return $out;
    }
    $out['card_key']   = (string)$row['card_key'];
    $out['old_status'] = (string)$row['status'];

    if ($out['old_status'] === $new) {
        $out['ok']     = true;
        $out['notice'] = '卡密 #' . $cardId . ' 本来就是 ' . $new . '，没有改动。';
        /* [GATEFIX] 幂等补一次：上次映射行要是没写成功（或库里被手工删了），这里顺手补回来 */
        bancard_after_status_toggle($out, $on);
        return $out;
    }

    try {
        db_run('UPDATE `cards` SET `status` = ? WHERE `id` = ?', array($new, $cardId));
    } catch (Throwable $e) {
        $out['error'] = '更新 cards.status 失败：' . $e->getMessage();
        return $out;
    }

    $out['ok']     = true;
    $out['notice'] = '卡密 #' . $cardId . ' 已' . ($on ? '禁用' : '启用') . '（' . $new . '，MySQL 即时生效）。'
        . '客户端要 ≤60 秒才会同步到 cards.json，或者去「仪表盘」点『立即同步』立刻生效。';
    bancard_after_status_toggle($out, $on);
    return $out;
}

/**
 * 某个玩家绑过的卡密（MySQL card_players 的两种口径：server_id / publisher_account_id）
 * @param int $serverId
 * @param int $publisherId
 * @return array card_id => array('card_id','card_key','status')
 */
function ban_cards_of_account($serverId, $publisherId = 0)
{
    $out = array();
    $serverId    = (int)$serverId;
    $publisherId = (int)$publisherId;
    if ($serverId <= 0 && $publisherId <= 0) {
        return $out;
    }
    if (function_exists('player_ensure_tables')) {
        try {
            player_ensure_tables();
        } catch (Throwable $e) {
            /* 建表失败也继续，下面查询会自己报错 */
        }
    }
    try {
        $rows = db_all(
            'SELECT c.id AS id, c.card_key AS card_key, c.status AS status
               FROM `cards` c
               JOIN `card_players` b ON b.card_id = c.id
              WHERE b.server_id = ? OR (b.publisher_account_id > 0 AND b.publisher_account_id = ?)
              ORDER BY c.id ASC',
            array($serverId, $publisherId)
        );
    } catch (Throwable $e) {
        return $out;
    }
    foreach ($rows as $r) {
        $cid = (int)$r['id'];
        $out[$cid] = array(
            'card_id'  => $cid,
            'card_key' => (string)$r['card_key'],
            'status'   => (string)$r['status'],
        );
    }
    return $out;
}

/* ============================================================================
 * 二·B [GATEFIX 2026-11-18] 卡密封禁 -> 账号封禁行（bans.kind='account'）
 *
 * 背景：客户端的封禁文案只在**游戏层**弹（桥 account_auth_probe.py 的 BAPATCH-BANREPLY，
 * 返回 Protocol=-1 / ErrorCode=1025 / BanReason）。桥只认 bans 表里 kind='account' 且
 * target=<publisherId> 的行，而"卡被封"是按卡密记的（kind='card'）。所以要一张映射：
 *
 *     付费卡 publisher = int(md5(卡密)[:8], 16) % 900000000 + 100000000
 *
 * 这个公式与 sdkcard.py 的 publisher_id()（paid 分支）**逐位一致**（算例见 NOTES.md §2）：
 * login 时 SDK 把这个数写进 User.ID，桥那边 DevId / EnterTicket 解出来的就是它，
 * 所以拿它做 target 就是"这张卡对应的那个账号"。
 *
 * 规矩（写死在这里，不要放宽）：
 *   ① 禁用（$on=true）：写/更新一行 bans(account, target=(string)$pub)，
 *      until_epoch 与卡密那条**完全一致**（永久=NULL，限时=同一个到期时间点）；
 *      reason = "卡密封禁 · <脱敏卡密>" —— 前缀固定，解封与对账只认这个前缀。
 *   ② 解封（$on=false）：**只删** reason 以「卡密封禁」开头的行。
 *      绝不能 banexp_clear('account', $pub) 一把梭：bans 表是 UNIQUE(kind,target)，
 *      手工账号封禁跟它可能正好是同一行，删掉就是放走一个真被封的账号。
 *   ③ 该 publisher 已经有**非卡密来源**的账号封禁行 -> 不覆盖，只在 warnings / 审计里说。
 *      宁可少做一步（放行方向），也不要把运营手工封的账号改短或改长。
 *   ④ 公益卡（kind='free'）不适用：它的账号是 md5("free:"+设备)，一台设备一个号，
 *      从卡密算不出来 ⇒ 不做映射，封禁继续由 SDK 层拦（NOTES.md §3）。
 *   ⑤ 全程 try/catch：写失败只记 warning + 审计，卡密状态照旧生效（NOTES.md §4）。
 * ========================================================================== */

if (!defined('BANCARD_REASON_PREFIX')) {
    define('BANCARD_REASON_PREFIX', '卡密封禁');
}

/** 映射行的 reason（前缀 + 脱敏卡密；面板「封禁管理」的原因列 30 字内能完整显示） */
function bancard_reason($cardKey)
{
    return BANCARD_REASON_PREFIX . ' · ' . banexp_mask_card((string)$cardKey);
}

/**
 * 付费卡 publisher：`int(md5(卡密)[:8], 16) % 900000000 + 100000000`
 * 必须与 sdkcard.py 的 publisher_id() 逐位一致（NOTES.md §2 有 3 组算例）。
 * @param string $cardKey
 * @return int
 */
function bancard_pub($cardKey)
{
    $key = (string)$cardKey;
    if ($key === '') {
        return 0;
    }
    return (int)(hexdec(substr(md5($key), 0, 8)) % 900000000) + 100000000;
}

/** 这张卡是 free 还是 paid（库还没有 kind 列时按 paid，与 sdkcard.py 的默认值一致） */
function bancard_card_kind($cardKey)
{
    static $hasCol = null;
    if ($hasCol === null) {
        $hasCol = false;
        try {
            $n = (int)db_val(
                "SELECT COUNT(*) FROM information_schema.COLUMNS
                  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cards' AND COLUMN_NAME = 'kind'",
                array(),
                0
            );
            $hasCol = ($n > 0);
        } catch (Throwable $e) {
            $hasCol = false;
        }
    }
    if (!$hasCol) {
        return 'paid';
    }
    try {
        $k = strtolower(trim((string)db_val(
            'SELECT `kind` FROM `cards` WHERE `card_key` = ? LIMIT 1',
            array((string)$cardKey),
            ''
        )));
    } catch (Throwable $e) {
        return 'paid';
    }
    return ($k === 'free') ? 'free' : 'paid';
}

/* --- 重入护栏：banexp_toggle_card() 内部会调 ban_card_toggle()，
 *     那条路径由 banexp_toggle_card() 自己带着 until_epoch 统一写，避免写两遍。 --- */
function bancard_sync_guard_push()
{
    $n = isset($GLOBALS['BANCARD_SYNC_DEPTH']) ? (int)$GLOBALS['BANCARD_SYNC_DEPTH'] : 0;
    $GLOBALS['BANCARD_SYNC_DEPTH'] = $n + 1;
}

function bancard_sync_guard_pop()
{
    $n = isset($GLOBALS['BANCARD_SYNC_DEPTH']) ? (int)$GLOBALS['BANCARD_SYNC_DEPTH'] : 0;
    $GLOBALS['BANCARD_SYNC_DEPTH'] = ($n > 0) ? ($n - 1) : 0;
}

function bancard_sync_guard()
{
    return (isset($GLOBALS['BANCARD_SYNC_DEPTH']) && (int)$GLOBALS['BANCARD_SYNC_DEPTH'] > 0);
}

/** 映射相关的审计（面板没有 audit_log() 或写失败都不影响主流程） */
function bancard_audit($action, $cardKey, $msg)
{
    if (!function_exists('audit_log')) {
        return;
    }
    try {
        audit_log((string)$action, '卡密 ' . banexp_mask_card((string)$cardKey), (string)$msg);
    } catch (Throwable $e) {
        /* ignore */
    }
}

/**
 * 卡密维度 -> 账号维度的那一步（写 / 删 / 跳过，全部幂等，绝不抛）。
 *
 * @param string   $cardKey
 * @param bool     $on         true=封禁，false=解封
 * @param int|null $untilEpoch null=永久；否则与卡密那条同一个到期时间点
 * @param string   $by         操作人（写进 bans.created_by）
 * @return array('ok'=>bool,'action'=>string,'error'=>string,'warning'=>string,
 *               'pub'=>int,'reason'=>string,'until_epoch'=>int|null,'kind'=>string)
 *         action = added | updated | deleted | keep-manual | skip-free | none | error
 */
function bancard_account_apply($cardKey, $on, $untilEpoch, $by = '')
{
    $out = array(
        'ok' => false, 'action' => 'error', 'error' => '', 'warning' => '',
        'pub' => 0, 'reason' => '', 'until_epoch' => null, 'kind' => '',
    );
    try {
        $key = trim((string)$cardKey);
        if ($key === '') {
            $out['error'] = '空卡密，算不出 publisher';
            return $out;
        }

        /* ④ 公益卡：账号按设备算，映射不出来 => 不做（SDK 层继续拦） */
        $kind = bancard_card_kind($key);
        $out['kind'] = $kind;
        if ($kind === 'free') {
            $out['ok']     = true;
            $out['action'] = 'skip-free';
            $out['warning'] = '公益卡的账号是 md5("free:"+设备)，与卡密无关，不做 publisher 映射；'
                . '它的封禁继续由 SDK 层拦（见 NOTES.md §3）';
            return $out;
        }

        $pub = bancard_pub($key);
        $out['pub'] = $pub;
        if ($pub <= 0) {
            $out['error'] = 'publisher 计算失败';
            return $out;
        }
        $ps  = (string)$pub;
        $row = banexp_row('account', $ps);      /* 任意来源的那一行（UNIQUE(kind,target)） */
        $isOurs = ($row !== null && strpos((string)$row['reason'], BANCARD_REASON_PREFIX) === 0);

        /* ---- 解封：只删自己写的那行 ---- */
        if (!$on) {
            if ($row === null) {
                $out['ok']     = true;
                $out['action'] = 'none';
                return $out;
            }
            if (!$isOurs) {
                $out['ok']     = true;
                $out['action'] = 'keep-manual';
                $out['warning'] = 'publisher ' . $ps . ' 的账号封禁不是卡密来源（reason 不以「'
                    . BANCARD_REASON_PREFIX . '」开头），没有删它';
                return $out;
            }
            $rc = banexp_clear('account', $ps);
            if (empty($rc['ok'])) {
                $out['error'] = '删账号封禁行失败：' . $rc['error'];
                return $out;
            }
            $out['ok']     = true;
            $out['action'] = 'deleted';
            bancard_audit('card.ban_account_clear', $key,
                '解封时删掉卡密封禁映射行 | publisher ' . $ps . ' | 影响 ' . (int)$rc['deleted'] . ' 行');
            return $out;
        }

        /* ---- 封禁：已有非卡密来源的行 -> 不覆盖（③） ---- */
        if ($row !== null && !$isOurs) {
            $out['ok']     = true;
            $out['action'] = 'keep-manual';
            $out['warning'] = 'publisher ' . $ps . ' 已有一条非卡密来源的账号封禁行，没有覆盖它；'
                . '这张卡仍然记在封禁表的卡密行里，人工确认一下更稳妥';
            bancard_audit('card.ban_account_keep', $key,
                '跳过覆盖：publisher ' . $ps . ' 已有手工账号封禁（reason='
                . substr((string)$row['reason'], 0, 60) . '）');
            return $out;
        }

        $until = ($untilEpoch === null || $untilEpoch === '' || (int)$untilEpoch <= 0)
            ? null : (int)$untilEpoch;
        $reason = bancard_reason($key);
        $ru = banexp_upsert('account', $ps, $until, $reason, (string)$by);
        if (empty($ru['ok'])) {
            $out['error'] = '写账号封禁行失败：' . $ru['error'];
            return $out;
        }
        $out['ok']          = true;
        $out['action']      = ($row === null) ? 'added' : 'updated';
        $out['reason']      = $reason;
        $out['until_epoch'] = $until;
        bancard_audit('card.ban_account', $key,
            '卡密封禁映射到账号维度 | publisher ' . $ps
            . ' | until=' . ($until === null ? 'NULL(永久)' : (string)$until)
            . ' | ' . $out['action']);
        return $out;
    } catch (Throwable $e) {
        $out['action'] = 'error';
        $out['error']  = '卡密封禁->账号封禁映射异常：' . $e->getMessage();
        return $out;
    }
}

/**
 * ban_card_toggle() 成功之后的"顺手一步"：只往 $out 里写字，不抛、不改 $out['ok']。
 * @param array $out ban_card_toggle() 的返回体（引用）
 * @param bool  $on
 * @return void
 */
function bancard_after_status_toggle(&$out, $on)
{
    if (bancard_sync_guard()) {
        return;   /* 由 banexp_toggle_card() 统一处理（它知道 until_epoch） */
    }
    $key = isset($out['card_key']) ? (string)$out['card_key'] : '';
    $map = bancard_account_apply($key, (bool)$on, null, 'bans.php');
    if (!isset($out['warnings']) || !is_array($out['warnings'])) {
        $out['warnings'] = array();
    }
    $out['bancard'] = $map;

    if (empty($map['ok'])) {
        $out['warnings'][] = '账号封禁行（游戏层拦截）没写成功：' . $map['error'];
        $out['notice'] .= ' ⚠ 账号封禁行没写成功（' . $map['error'] . '）：'
            . '玩家仍然能进游戏（失败方向是放行，不会误封），请再点一次或到「封禁管理」手动处理。';
        bancard_audit('card.ban_account_fail', $key, '卡密封禁映射失败：' . $map['error']);
        return;
    }
    if ($map['action'] === 'skip-free') {
        $out['notice'] .= ' 公益卡不做 publisher 映射：封禁仍由 SDK 层拦（玩家到不了游戏层）。';
        return;
    }
    if ($map['action'] === 'keep-manual') {
        $out['warnings'][] = $map['warning'];
        $out['notice'] .= ' 注意：' . $map['warning'] . '。';
        return;
    }
    if ($map['action'] === 'deleted') {
        $out['notice'] .= ' 已删掉账号封禁映射行（publisher ' . (int)$map['pub'] . '）。';
        return;
    }
    if ($map['action'] === 'none') {
        return;
    }
    $out['notice'] .= ' 已同时' . ($map['action'] === 'added' ? '写入' : '更新')
        . '账号封禁行（publisher ' . (int)$map['pub']
        . '）：桥会回官方封禁包（ErrorCode 1025 + BanReason）。';
}

/* ============================================================================
 * 三、账号封禁（Shittim Accounts.State）与硬删除
 * ========================================================================== */

/**
 * 封禁 / 解封一个账号：Shittim `Accounts.State`，2=Dormant（封）/ 1=Normal（解）。
 * 只动账号这一个维度，不会碰卡密与设备。
 *
 * @param int  $serverId
 * @param bool $on
 * @return array('ok'=>bool,'error'=>string,'notice'=>string,'server_id'=>int,'state'=>int,'ms'=>int)
 */
function ban_account_toggle($serverId, $on)
{
    $serverId = (int)$serverId;
    $out = array(
        'ok' => false, 'error' => '', 'notice' => '',
        'server_id' => $serverId, 'state' => $on ? 2 : 1, 'ms' => 0,
    );
    if ($serverId <= 0) {
        $out['error'] = 'ServerId 无效';
        return $out;
    }

    $r = ba_account_update($serverId, array('State' => $on ? 2 : 1));
    $out['ms'] = isset($r['ms']) ? (int)$r['ms'] : 0;

    if (empty($r['ok'])) {
        $err = isset($r['error']) ? trim((string)$r['error']) : '';
        if ($err === '' && isset($r['status'])) {
            $err = 'HTTP ' . (int)$r['status'];
        }
        $out['error'] = $err === '' ? '调用 Shittim /api/admin/account/update 失败' : $err;
        return $out;
    }

    $out['ok']     = true;
    $out['notice'] = '账号 ' . $serverId . ' 已' . ($on ? '封禁' : '解封') . '（State='
        . ($on ? '2 Dormant' : '1 Normal') . '，下次登录生效）。本次没有动卡密和设备。';
    return $out;
}

/**
 * 硬删除一个账号：
 *   ① 先调 Shittim POST /api/admin/account/delete（服务端级联清所有带 AccountServerId 的表 + Accounts + UserAccounts）
 *   ② **成功之后**再删桥接 accounts.db 里 `shittim_server_id = $serverId` 的那行（NULL 行一律不删）
 *
 * @param int $serverId
 * @return array('ok'=>bool,'error'=>string,'bridge_rows'=>int,'warning'=>string,'notice'=>string,'server_id'=>int)
 */
function ban_delete_account($serverId)
{
    $serverId = (int)$serverId;
    $out = array(
        'ok' => false, 'error' => '', 'bridge_rows' => 0, 'warning' => '',
        'card_player_rows' => 0,
        'notice' => '', 'server_id' => $serverId,
    );
    if ($serverId <= 0) {
        $out['error'] = 'ServerId 无效';
        return $out;
    }

    /* --- ① Shittim 硬删除 --- */
    $r = ba_post('/api/admin/account/delete', array('ServerId' => $serverId));
    if (empty($r['ok'])) {
        $err = isset($r['error']) ? trim((string)$r['error']) : '';
        if ($err === '' && isset($r['status'])) {
            $err = 'HTTP ' . (int)$r['status'];
        }
        $out['error'] = 'Shittim 删除失败：' . ($err === '' ? '未知错误' : $err) . '（桥接 accounts.db 未改动）';
        return $out;
    }
    $out['ok'] = true;

    /* --- ② 桥接 accounts.db（成功后才做；NULL 行不动） --- */
    $path = function_exists('player_accounts_db_path') ? player_accounts_db_path() : '';
    if ($path === '' || !is_file($path)) {
        $out['warning'] = '桥接账号库不存在，桥侧未清理：' . $path;
        $out['notice']  = '已从 Shittim 硬删除账号 ' . $serverId . '（桥接库不存在，未做桥侧清理）。';
        return $out;
    }
    if (!class_exists('PDO') || !in_array('sqlite', PDO::getAvailableDrivers(), true)) {
        $out['warning'] = 'PHP 未启用 pdo_sqlite，桥侧未清理';
        $out['notice']  = '已从 Shittim 硬删除账号 ' . $serverId . '（无 pdo_sqlite，桥接库未清理）。';
        return $out;
    }

    try {
        $pdo = new PDO('sqlite:' . $path, null, null, array(
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_TIMEOUT            => 5,
        ));
        $cols = array();
        foreach ($pdo->query('PRAGMA table_info(accounts)') as $c) {
            if (isset($c['name'])) {
                $cols[strtolower((string)$c['name'])] = true;
            }
        }
        if (!isset($cols['shittim_server_id'])) {
            $out['warning'] = '桥接库没有 shittim_server_id 列（老库未迁移），桥侧未删任何行';
        } else {
            $st = $pdo->prepare('DELETE FROM accounts WHERE shittim_server_id IS NOT NULL AND shittim_server_id = ?');
            $st->execute(array($serverId));
            $out['bridge_rows'] = (int)$st->rowCount();
        }
    } catch (Throwable $e) {
        $out['warning'] = '桥接库删除失败：' . $e->getMessage();
    }

    /* --- [DEVFIX 2026-11-18] ③ card_players（MySQL，面板自建表）：把指向这个 ServerId 的绑定清零 ---
     * 以前删号只清 Shittim + accounts.db，**完全没碰 card_players**，
     * 结果 card_players.server_id 会永远停在被删的那个号上
     * （实测：8 号卡记 7，删号重建后实际已是 9）。
     *
     * 这里只把 server_id 清 0，**不删行、不动 publisher_account_id**：
     *   · roster 优先按 publisher 匹配，pub 还在，玩家归属不会丢；
     *   · 清 0 之后 1 分钟内 player_autobind_cards() 会把新 ServerId 补回来；
     *   · manual 绑定因此不会被"删号"这个动作摧毁。
     */
    try {
        $cp = db_run('UPDATE card_players SET server_id = 0 WHERE server_id = ?', array((int)$serverId));
        $out['card_player_rows'] = is_object($cp) ? (int)$cp->rowCount() : 0;
    } catch (Throwable $e) {
        $out['warning'] = trim((string)$out['warning'] . ' card_players 同步失败：' . $e->getMessage());
    }

    $out['notice'] = '已从 Shittim 硬删除账号 ' . $serverId . '（不可恢复）'
        . ($out['bridge_rows'] > 0
            ? '，桥接 accounts.db 清掉 ' . $out['bridge_rows'] . ' 行'
            : '，桥接 accounts.db 没有 shittim_server_id 匹配的行')
        . ((int)$out['card_player_rows'] > 0
            ? '，卡密绑定 server_id 清零 ' . (int)$out['card_player_rows'] . ' 行'
            : '');
    return $out;
}

/* ============================================================================
 * 四、聚合读（给页面渲染用）
 * ========================================================================== */

/**
 * Shittim 账号列表（一次性拉全量并索引，避免页面每行都打一次 API）
 * @param bool $reload
 * @return array('ok'=>bool,'error'=>string,'rows'=>array serverId=>原始行,'ms'=>int)
 */
function ban_accounts_index($reload = false)
{
    static $cache = null;
    if ($cache !== null && !$reload) {
        return $cache;
    }
    $cache = array('ok' => false, 'error' => '', 'rows' => array(), 'ms' => 0);

    $r = ba_accounts();
    $cache['ms'] = isset($r['ms']) ? (int)$r['ms'] : 0;
    if (empty($r['ok']) || !isset($r['data']) || !is_array($r['data'])) {
        $err = isset($r['error']) ? trim((string)$r['error']) : '';
        $cache['error'] = $err !== '' ? $err : '读取 Shittim 账号列表失败';
        return $cache;
    }
    foreach ($r['data'] as $a) {
        if (!isset($a['serverId'])) {
            continue;
        }
        $cache['rows'][(int)$a['serverId']] = $a;
    }
    $cache['ok'] = true;
    return $cache;
}

/**
 * 一次拿到三个维度的状态，供页面渲染。
 *
 * @param int    $serverId 0 = 不查账号
 * @param int    $cardId   0 = 不查卡密
 * @param string $dev      '' = 不查设备
 * @return array('account'=>array,'card'=>array,'device'=>array)
 */
function ban_status_of($serverId, $cardId = 0, $dev = '')
{
    $serverId = (int)$serverId;
    $cardId   = (int)$cardId;
    $dev      = trim((string)$dev);

    $out = array(
        'account' => array(
            'server_id' => $serverId, 'state' => '', 'label' => '', 'banned' => false,
            'error' => '', 'nickname' => '', 'publisher_id' => 0,
        ),
        'card' => array(
            'card_id' => $cardId, 'card_key' => '', 'status' => '', 'banned' => false, 'error' => '',
        ),
        'device' => array(
            'device' => $dev, 'banned' => false, 'error' => '',
        ),
    );

    /* 账号 */
    if ($serverId > 0) {
        $idx = ban_accounts_index();
        if (!$idx['ok']) {
            $out['account']['error'] = $idx['error'];
        } elseif (isset($idx['rows'][$serverId])) {
            $a     = $idx['rows'][$serverId];
            $state = isset($a['state']) ? (string)$a['state'] : '';
            $out['account']['state']   = $state;
            $out['account']['label']   = function_exists('player_state_label') ? player_state_label($state) : $state;
            $out['account']['banned']  = function_exists('player_is_banned')
                ? player_is_banned($state)
                : (strcasecmp($state, 'Dormant') === 0);
            $out['account']['nickname'] = isset($a['nickname']) ? (string)$a['nickname'] : '';
            $out['account']['publisher_id'] = isset($a['publisherAccountId']) ? (int)$a['publisherAccountId'] : 0;
        } else {
            $out['account']['error'] = 'Shittim 里没有 ServerId=' . $serverId . '（可能已被删除）';
        }
    }

    /* 卡密 */
    if ($cardId > 0) {
        try {
            $row = db_row('SELECT `id`, `card_key`, `status` FROM `cards` WHERE `id` = ? LIMIT 1', array($cardId));
            if (!$row) {
                $out['card']['error'] = '找不到卡密 #' . $cardId;
            } else {
                $out['card']['card_key'] = (string)$row['card_key'];
                $out['card']['status']   = (string)$row['status'];
                $out['card']['banned']   = ((string)$row['status'] !== 'active');
            }
        } catch (Throwable $e) {
            $out['card']['error'] = '数据库不可用：' . $e->getMessage();
        }
    }

    /* 设备 */
    if ($dev !== '') {
        try {
            $out['device']['banned'] = ban_device_has($dev);
        } catch (Throwable $e) {
            $out['device']['error'] = $e->getMessage();
        }
    }

    return $out;
}

/**
 * 某个玩家名下的设备（桥接库 + cards.json/card_devices 里「绑过他卡」的设备）
 * @param int $serverId
 * @param int $publisherId
 * @return array 设备号数组（去重）
 */
function ban_devices_of_account($serverId, $publisherId = 0)
{
    $serverId    = (int)$serverId;
    $publisherId = (int)$publisherId;
    $devs = array();
    if ($serverId <= 0) {
        return $devs;
    }

    /* [DEVFIX2 2026-11-18] 原来这里从桥接库取 accounts.device_unique_id / dev_id 当"设备"。
     * 两个都不是 SDK 认的设备号（device_unique_id 是桥自己算的 32 位串、没有任何一层拦它；
     * dev_id 是 publisherId 的副本）。封了不生效，整段去掉。
     * 真设备号从下面的 $cand 来（cards.json / card_devices / device_ban.txt）。
     */

    $cardKeys = array();
    foreach (ban_cards_of_account($serverId, $publisherId) as $c) {
        $cardKeys[(string)$c['card_key']] = true;
    }
    $cand = ban_device_candidates();
    foreach ($cand['devices'] as $d => $info) {
        $hit = isset($info['accounts'][$serverId]);
        if (!$hit && !empty($info['cards'])) {
            foreach ($info['cards'] as $ck) {
                if (isset($cardKeys[$ck])) {
                    $hit = true;
                    break;
                }
            }
        }
        if ($hit) {
            $devs[(string)$d] = true;
        }
    }

    $list = array_keys($devs);
    sort($list);
    return $list;
}

/**
 * 三个维度的汇总计数（页面顶部三张卡片用，只读、全部容错）
 * @return array
 */
function ban_summary()
{
    $out = array(
        'ok'      => true,
        'error'   => '',
        'account' => array('total' => 0, 'banned' => 0, 'api_ok' => false, 'error' => '', 'ms' => 0),
        'card'    => array('total' => 0, 'disabled' => 0, 'db_ok' => false, 'error' => ''),
        'device'  => array(
            'count' => 0, 'known' => 0, 'path' => '', 'writable' => false,
            'file_ok' => false, 'file_error' => '', 'bytes' => 0, 'mtime' => 0,
        ),
    );

    $idx = ban_accounts_index();
    $out['account']['api_ok'] = $idx['ok'];
    $out['account']['ms']     = $idx['ms'];
    if ($idx['ok']) {
        $out['account']['total'] = count($idx['rows']);
        $n = 0;
        foreach ($idx['rows'] as $a) {
            $state = isset($a['state']) ? (string)$a['state'] : '';
            $banned = function_exists('player_is_banned')
                ? player_is_banned($state)
                : (strcasecmp($state, 'Dormant') === 0);
            if ($banned) {
                $n++;
            }
        }
        $out['account']['banned'] = $n;
    } else {
        $out['account']['error'] = $idx['error'];
    }

    try {
        $out['card']['total']    = (int)db_val('SELECT COUNT(*) FROM `cards`', array(), 0);
        $out['card']['disabled'] = (int)db_val("SELECT COUNT(*) FROM `cards` WHERE `status` <> 'active'", array(), 0);
        $out['card']['db_ok']    = true;
    } catch (Throwable $e) {
        $out['card']['error'] = '数据库不可用：' . $e->getMessage();
    }

    $fs = ban_device_file_status();
    $out['device']['path']       = $fs['path'];
    $out['device']['file_ok']    = ($fs['error'] === '');
    $out['device']['file_error'] = $fs['error'];
    $out['device']['count']      = (int)$fs['count'];
    $out['device']['bytes']      = (int)$fs['bytes'];
    $out['device']['mtime']      = (int)$fs['mtime'];
    $out['device']['writable']   = ($fs['writable'] || $fs['dir_writable']);

    $cand = ban_device_candidates();
    $out['device']['known'] = (int)$cand['count'];

    return $out;
}

/* ============================================================================
 * 五、限时 / 永久封禁表（bans）—— 三个维度共用一张表，判定各自独立
 *
 * 表在桥接库 /www/wwwroot/bapatch/data/accounts.db 里，**只在读取方判到期**：
 *     until_epoch IS NULL                            -> 永久
 *     until_epoch IS NOT NULL AND until_epoch <= now -> 已到期 = 未封禁（边界：等于 now 也算过期）
 *     until_epoch IS NOT NULL AND until_epoch  > now -> 封禁中
 * 没有任何定时任务参与；本文件也不会去 ALTER/DROP 任何既有表（尤其不动 accounts）。
 *
 * 三个维度的写入策略（各自独立；"永久"才动旧机制，限时只写新表 —— 理由见 CHECK.md §2.4）：
 *   账号：bans(kind='account', target=<publisher_account_id>) + Shittim State 2/1（永久与限时都写
 *         State，保证拦得住；到期由桥的读侧自愈 + 本页 sweep 把 State 还原成 1）
 *   卡密：bans(kind='card', target=<card_key>) + cards.status（**仅永久**；限时不动 status，
 *         否则到期后 sync.php 不会再把卡导回 cards.json，卡就永远回不来）
 *   设备：bans(kind='device', target=<device>) + device_ban.txt（**仅永久**；同上，文件里的行不会自己过期）
 * ========================================================================== */

if (!defined('BANEXP_TZ')) {
    define('BANEXP_TZ', 'Asia/Shanghai');
}
if (!defined('BANEXP_DEFAULT_DB')) {
    define('BANEXP_DEFAULT_DB', '/www/wwwroot/bapatch/data/accounts.db');
}
/* 面板其余时间显示都走 date()，这里把它钉在 Asia/Shanghai（db.php 已经设过，这里只兜底） */
if (function_exists('date_default_timezone_set')) {
    @date_default_timezone_set(BANEXP_TZ);
}

/* ------------------------------------------------------------------ 5.1 表 --- */

/**
 * bans 表所在库的路径：常量 BA_BANS_DB > 桥接库（player_accounts_db_path） > 默认路径
 * @return string
 */
function banexp_db_path()
{
    static $path = null;
    if ($path !== null) {
        return $path;
    }
    $path = '';
    if (defined('BA_BANS_DB') && (string)BA_BANS_DB !== '') {
        $path = (string)BA_BANS_DB;
    }
    if ($path === '' && function_exists('player_accounts_db_path')) {
        try {
            $path = trim((string)player_accounts_db_path());
        } catch (Throwable $e) {
            $path = '';
        }
    }
    if ($path === '') {
        $path = BANEXP_DEFAULT_DB;
    }
    return $path;
}

/**
 * 建表语句（与 schema.sql 逐字一致；幂等）
 * @return array 语句数组
 */
function banexp_schema_sql()
{
    return array(
        "CREATE TABLE IF NOT EXISTS bans (\n"
        . "    id          INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        . "    kind        TEXT    NOT NULL CHECK (kind IN ('account', 'card', 'device')),\n"
        . "    target      TEXT    NOT NULL,\n"
        . "    until_epoch INTEGER     NULL,\n"
        . "    reason      TEXT    NOT NULL DEFAULT '',\n"
        . "    created_at  TEXT    NOT NULL,\n"
        . "    created_by  TEXT    NOT NULL DEFAULT '',\n"
        . "    UNIQUE (kind, target)\n"
        . ")",
        'CREATE INDEX IF NOT EXISTS idx_bans_until ON bans (until_epoch)',
        'CREATE INDEX IF NOT EXISTS idx_bans_kind_until ON bans (kind, until_epoch)',
    );
}

/**
 * 可读写的 PDO（sqlite）。不可用时返回 null（页面自己降级显示）。
 * @return PDO|null
 */
function banexp_pdo()
{
    static $pdo = null;
    static $tried = false;
    if ($tried) {
        return $pdo;
    }
    $tried = true;
    $pdo   = null;
    if (!class_exists('PDO') || !in_array('sqlite', PDO::getAvailableDrivers(), true)) {
        return null;
    }
    /* 库不存在就不要用 PDO 去"打开"它：sqlite 会**新建一个空库**，等于在错路径下造假数据。 */
    if (!is_file(banexp_db_path())) {
        return null;
    }
    try {
        $pdo = new PDO('sqlite:' . banexp_db_path(), null, null, array(
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_TIMEOUT            => 5,
        ));
    } catch (Throwable $e) {
        $pdo = null;
    }
    return $pdo;
}

/**
 * 幂等建表（每次进程只做一次；失败不抛，返回 false）
 * @return bool
 */
function banexp_ensure_schema($reload = false)
{
    static $ok = null;
    if ($ok !== null && !$reload) {
        return $ok;
    }
    $ok  = false;
    $pdo = banexp_pdo();
    if (!$pdo) {
        return false;
    }
    try {
        foreach (banexp_schema_sql() as $sql) {
            $pdo->exec($sql);
        }
        $ok = true;
    } catch (Throwable $e) {
        /* 表已存在但 CHECK/索引没建成功之类：只要能读就继续 */
        try {
            $st = $pdo->query('SELECT COUNT(*) AS n FROM bans');
            $ok = ($st !== false);
        } catch (Throwable $e2) {
            $ok = false;
        }
    }
    return $ok;
}

/* -------------------------------------------------------------- 5.2 读/判定 --- */

/**
 * 读全表（进程内缓存；写操作后传 $reload=true 刷新）
 * @param bool $reload
 * @return array('ok'=>bool,'error'=>string,'rows'=>array id=>row,'index'=>array "kind\ttarget"=>row)
 */
function banexp_all($reload = false)
{
    static $cache = null;
    if ($cache !== null && !$reload) {
        return $cache;
    }
    $cache = array('ok' => false, 'error' => '', 'rows' => array(), 'index' => array());
    if (!banexp_ensure_schema()) {
        $cache['error'] = '封禁表不可用：' . banexp_db_path() . '（PHP 需要 pdo_sqlite，且该文件可读写）';
        return $cache;
    }
    $pdo = banexp_pdo();
    try {
        $st = $pdo->query('SELECT `id`, `kind`, `target`, `until_epoch`, `reason`, `created_at`, `created_by`'
            . ' FROM `bans` ORDER BY `id` ASC');
        foreach ($st as $r) {
            $row = array(
                'id'          => (int)$r['id'],
                'kind'        => (string)$r['kind'],
                'target'      => (string)$r['target'],
                'until_epoch' => ($r['until_epoch'] === null) ? null : (int)$r['until_epoch'],
                'reason'      => (string)$r['reason'],
                'created_at'  => (string)$r['created_at'],
                'created_by'  => (string)$r['created_by'],
            );
            $cache['rows'][$row['id']] = $row;
            $cache['index'][$row['kind'] . "\t" . $row['target']] = $row;
        }
    } catch (Throwable $e) {
        $cache['error'] = '读封禁表失败：' . $e->getMessage();
        return $cache;
    }
    $cache['ok'] = true;
    return $cache;
}

/**
 * 单行查询
 * @param string $kind
 * @param string $target
 * @return array|null
 */
function banexp_row($kind, $target)
{
    $kind   = (string)$kind;
    $target = (string)$target;
    if ($target === '') {
        return null;
    }
    $all = banexp_all();
    $k   = $kind . "\t" . $target;
    return isset($all['index'][$k]) ? $all['index'][$k] : null;
}

/**
 * 到期判定（三端同一条规则；$now 便于自测/对齐）
 * @param array|null $row
 * @param int|null   $now
 * @return bool
 */
function banexp_is_active($row, $now = null)
{
    if (!is_array($row)) {
        return false;
    }
    $now = ($now === null) ? time() : (int)$now;
    $u   = isset($row['until_epoch']) ? $row['until_epoch'] : null;
    if (banexp_is_permanent($u)) {
        return true;                      /* 永久 */
    }
    return ((int)$u) > $now;              /* 等于 now 也算已到期 */
}

/**
 * until_epoch 是否算"永久"（与 ban_message.py 的 is_permanent() 同一套判定）
 *   null / true|false / '' / 非数字字符串  -> 永久
 *   整数 / 浮点 / 数字字符串              -> 限时
 * @param mixed $untilEpoch
 * @return bool
 */
function banexp_is_permanent($untilEpoch)
{
    if ($untilEpoch === null || is_bool($untilEpoch)) {
        return true;
    }
    if (is_string($untilEpoch) && trim($untilEpoch) === '') {
        return true;
    }
    if (is_int($untilEpoch) || is_float($untilEpoch)) {
        return false;
    }
    if (is_string($untilEpoch) && is_numeric(trim($untilEpoch))) {
        return false;
    }
    return true;
}

/**
 * created_at（'Y-m-d H:i:s'，Asia/Shanghai）-> epoch；解析不出来返回 null
 * @param mixed $createdAt
 * @return int|null
 */
function banexp_created_epoch($createdAt)
{
    if ($createdAt === null) {
        return null;
    }
    if (is_int($createdAt)) {
        return $createdAt;
    }
    $s = trim((string)$createdAt);
    if ($s === '') {
        return null;
    }
    if (ctype_digit($s)) {
        return (int)$s;
    }
    $s = str_replace('T', ' ', $s);
    if (substr($s, -1) === 'Z') {
        $s = rtrim(substr($s, 0, -1));
    }
    foreach (array('Y-m-d H:i:s', 'Y-m-d H:i') as $fmt) {
        $dt = DateTime::createFromFormat($fmt, $s, new DateTimeZone(BANEXP_TZ));
        if ($dt instanceof DateTime) {
            return (int)$dt->getTimestamp();
        }
    }
    $ts = strtotime($s);
    return ($ts === false) ? null : (int)$ts;
}

/**
 * epoch -> 'Y-m-d H:i'（Asia/Shanghai）—— 文案与列表都用这一个格式
 * @param int $epoch
 * @return string
 */
function ban_msg_time($epoch)
{
    return date('Y-m-d H:i', (int)$epoch);
}

/**
 * 【文案统一函数 · PHP 侧】与 ban_message.py 的 ban_message() 逐字一致：
 *
 *   永久（until 为 null/''）-> '封禁，请联系客服'
 *   限时                    -> '封号时间 2026-11-18 20:00 至 2026-11-20 20:00，请联系客服'
 *
 * @param int|null     $untilEpoch
 * @param int|null     $startEpoch 起点（= bans.created_at 的 epoch）；缺省则退化成"起点 = 终点"
 * @return string
 */
function ban_msg($untilEpoch, $startEpoch = null)
{
    if (banexp_is_permanent($untilEpoch)) {
        return '封禁，请联系客服';
    }
    $end = ban_msg_time((int)$untilEpoch);
    $beg = ($startEpoch === null || $startEpoch === '') ? '' : ban_msg_time((int)$startEpoch);
    if ($beg === '') {
        $beg = $end;
    }
    return sprintf('封号时间 %s 至 %s，请联系客服', $beg, $end);
}

/**
 * 一行 -> 文案（起点从 created_at 解析）
 * @param array $row
 * @return string
 */
function banexp_msg($row)
{
    if (!is_array($row)) {
        return '封禁，请联系客服';
    }
    $until = isset($row['until_epoch']) ? $row['until_epoch'] : null;
    $start = banexp_created_epoch(isset($row['created_at']) ? $row['created_at'] : null);
    return ban_msg($until, $start);
}

/**
 * 一行 -> 列表展示文案
 * @param array|null $row
 * @param int|null   $now
 * @return string
 */
function banexp_status_line($row, $now = null)
{
    if (!is_array($row)) {
        return '未封禁';
    }
    if (!banexp_is_active($row, $now)) {
        return '已到期（未封禁）· 至 ' . ban_msg_time((int)$row['until_epoch']);
    }
    if ($row['until_epoch'] === null) {
        return '封禁中 · 永久';
    }
    return '封禁中 · 至 ' . ban_msg_time((int)$row['until_epoch']);
}

/* ------------------------------------------------------------------ 5.3 写 --- */

/**
 * 规范化一个 target / kind（写库前统一口径，避免 "  123 " 与 "123" 变成两行）
 * @param string $kind
 * @param string $target
 * @return array('ok'=>bool,'error'=>string,'kind'=>string,'target'=>string)
 */
function banexp_norm($kind, $target)
{
    $out  = array('ok' => false, 'error' => '', 'kind' => '', 'target' => '');
    $kind = trim((string)$kind);
    if (!in_array($kind, array('account', 'card', 'device'), true)) {
        $out['error'] = '封禁类型无效：' . banexp_cut($kind, 20);
        return $out;
    }
    $target = trim((string)$target);
    if ($target === '') {
        $out['error'] = '封禁目标为空';
        return $out;
    }
    if (strlen($target) > 200) {
        $out['error'] = '封禁目标过长（>200 字节）';
        return $out;
    }
    if (preg_match('/[\r\n\t]/', $target) !== 0) {
        $out['error'] = '封禁目标里不能有换行/制表符';
        return $out;
    }
    $out['ok']     = true;
    $out['kind']   = $kind;
    $out['target'] = $target;
    return $out;
}

/**
 * 写一行（存在则覆盖 until/reason/created_at/created_by；created_at 每次重封都刷新，
 * 这样"封号时间 <起点> 至 <终点>"里的起点就是本次封禁的时间）。
 *
 * @param string   $kind
 * @param string   $target
 * @param int|null $untilEpoch null = 永久
 * @param string   $reason
 * @param string   $by
 * @return array('ok'=>bool,'error'=>string,'kind'=>string,'target'=>string,'until_epoch'=>int|null,'created_at'=>string,'id'=>int)
 */
function banexp_upsert($kind, $target, $untilEpoch, $reason = '', $by = '')
{
    $out = array(
        'ok' => false, 'error' => '', 'kind' => '', 'target' => '',
        'until_epoch' => null, 'created_at' => '', 'id' => 0,
    );
    $n = banexp_norm($kind, $target);
    if (!$n['ok']) {
        $out['error'] = $n['error'];
        return $out;
    }
    $out['kind']   = $n['kind'];
    $out['target'] = $n['target'];

    $until = null;
    if ($untilEpoch !== null && $untilEpoch !== '') {
        $until = (int)$untilEpoch;
        if ($until <= 0) {
            $out['error'] = '封禁到期时间无效';
            return $out;
        }
    }
    $out['until_epoch'] = $until;
    $out['created_at']  = date('Y-m-d H:i:s');
    $reason             = trim((string)$reason);
    if (strlen($reason) > 500) {
        $reason = substr($reason, 0, 500);
    }
    $by = trim((string)$by);
    if (strlen($by) > 100) {
        $by = substr($by, 0, 100);
    }

    if (!banexp_ensure_schema()) {
        $out['error'] = '封禁表不可用：' . banexp_db_path();
        return $out;
    }
    $pdo = banexp_pdo();
    if (!$pdo) {
        $out['error'] = 'PHP 没有 pdo_sqlite，写不了封禁表';
        return $out;
    }

    try {
        $pdo->beginTransaction();
        $st = $pdo->prepare('SELECT `id` FROM `bans` WHERE `kind` = ? AND `target` = ? LIMIT 1');
        $st->execute(array($n['kind'], $n['target']));
        $row = $st->fetch(PDO::FETCH_ASSOC);
        if ($row) {
            $up = $pdo->prepare('UPDATE `bans` SET `until_epoch` = ?, `reason` = ?, `created_at` = ?, `created_by` = ? WHERE `id` = ?');
            $up->execute(array($until, $reason, $out['created_at'], $by, (int)$row['id']));
            $out['id'] = (int)$row['id'];
        } else {
            $in = $pdo->prepare('INSERT INTO `bans` (`kind`, `target`, `until_epoch`, `reason`, `created_at`, `created_by`)'
                . ' VALUES (?, ?, ?, ?, ?, ?)');
            $in->execute(array($n['kind'], $n['target'], $until, $reason, $out['created_at'], $by));
            $out['id'] = (int)$pdo->lastInsertId();
        }
        $pdo->commit();
    } catch (Throwable $e) {
        try {
            if ($pdo->inTransaction()) {
                $pdo->rollBack();
            }
        } catch (Throwable $e2) {
            /* ignore */
        }
        $out['error'] = '写封禁表失败：' . $e->getMessage();
        return $out;
    }

    banexp_all(true);
    $out['ok'] = true;
    return $out;
}

/**
 * 删一行（解封）
 * @param string $kind
 * @param string $target
 * @return array('ok'=>bool,'error'=>string,'deleted'=>int)
 */
function banexp_clear($kind, $target)
{
    $out = array('ok' => false, 'error' => '', 'deleted' => 0);
    $n = banexp_norm($kind, $target);
    if (!$n['ok']) {
        $out['error'] = $n['error'];
        return $out;
    }
    if (!banexp_ensure_schema()) {
        $out['error'] = '封禁表不可用：' . banexp_db_path();
        return $out;
    }
    $pdo = banexp_pdo();
    if (!$pdo) {
        $out['error'] = 'PHP 没有 pdo_sqlite，写不了封禁表';
        return $out;
    }
    try {
        $st = $pdo->prepare('DELETE FROM `bans` WHERE `kind` = ? AND `target` = ?');
        $st->execute(array($n['kind'], $n['target']));
        $out['deleted'] = (int)$st->rowCount();
        $out['ok']      = true;
    } catch (Throwable $e) {
        $out['error'] = '删封禁行失败：' . $e->getMessage();
        return $out;
    }
    banexp_all(true);
    return $out;
}

/* ------------------- 5.3.1 「清理到期行」：先还原 State，再删行 ------------------- */

/**
 * 单次「清理到期记录」最多给多少个账号行还原 State（防止积压几百行时把页面拖死）。
 * 超过上限的行**原样保留**（绝不删），下次再点按钮继续处理。
 */
if (!defined('BANEXP_PURGE_MAX_RELEASE')) {
    define('BANEXP_PURGE_MAX_RELEASE', 200);
}

/**
 * publisher_account_id -> Shittim ServerId（只读，不写任何东西）。
 *
 * 解析顺序：
 *   ① 桥接 accounts.db 的 accounts 表：`publisher_account_id = $publisherId` 那一行的
 *      `shittim_server_id`（可能是 NULL）。player_bridge_accounts() 已经把整表按
 *      publisher_account_id 读进内存，这里不额外查库、也不新写 SQL。
 *   ② ① 拿不到（列是 NULL / 没有这行 / 老库没这个列）时，退到 Shittim 账号列表按
 *      `publisherAccountId` 反查（ban_accounts_index() 进程内已缓存，不是每行一次 API）。
 *
 * @param int $publisherId
 * @return array('server_id'=>int,'source'=>string,'index_ok'=>bool)
 *         source   = accounts_db | shittim_index | none
 *         index_ok = 有没有拿到 Shittim 账号列表。false 表示"现在根本判定不了"
 *                    （调用方据此选择**保留行**，不要在 Shittim 不可达时盲删账号行）
 */
function banexp_purge_resolve_sid($publisherId)
{
    $out = array('server_id' => 0, 'source' => 'none', 'index_ok' => false);
    $pub = (int)$publisherId;
    if ($pub <= 0) {
        return $out;
    }

    if (function_exists('player_bridge_accounts')) {
        try {
            $bridge = player_bridge_accounts();
            $key    = (string)$pub;
            if (isset($bridge[$key]) && is_array($bridge[$key])) {
                $sid = isset($bridge[$key]['shittim_server_id']) ? (int)$bridge[$key]['shittim_server_id'] : 0;
                if ($sid > 0) {
                    $out['server_id'] = $sid;
                    $out['source']    = 'accounts_db';
                    $out['index_ok']  = true;
                    return $out;
                }
            }
        } catch (Throwable $e) {
            /* 桥接库读不到：当作没解析到，继续走 ② */
        }
    }

    $idx = ban_accounts_index();
    $out['index_ok'] = !empty($idx['ok']);
    if (!empty($idx['ok']) && !empty($idx['rows'])) {
        foreach ($idx['rows'] as $sid => $a) {
            $p = isset($a['publisherAccountId']) ? (int)$a['publisherAccountId'] : 0;
            if ($p === $pub && (int)$sid > 0) {
                $out['server_id'] = (int)$sid;
                $out['source']    = 'shittim_index';
                return $out;
            }
        }
    }
    return $out;
}

/**
 * 删掉所有已到期的行（三个维度；只删 until_epoch <= now 的，永久行一条不动）。
 *
 * 【修复点 · 2026-11-18】账号维度必须**先还原 Shittim State、再删行**，顺序与
 * banexp_sweep_account_releases() 完全一致。旧实现只 DELETE 行，后果是永久锁死：
 *   行没了 ⇒ 桥 banexp_account_row() 查不到 ⇒ 返回 none ⇒ 永不自愈；
 *   本页 sweep 又只在 banexp_summary()['account']['expired'] > 0 时动手 ⇒ 0 ⇒ 也不动手；
 *   ⇒ Shittim 侧 State 停在 2(Dormant)，两端都不再碰它，玩家永久进不去。
 *
 * 固定顺序（每一步都可重入，重复点按钮是安全的）：
 *   ① 查到期行
 *   ② 账号行：publisher -> ServerId（banexp_purge_resolve_sid()）-> ban_account_toggle($sid,false)
 *        · 还原成功         -> 删行，计 released
 *        · 还原失败         -> **保留行**（留一条重试路径；删掉就变孤儿封禁），计 failed
 *        · 解析不到 ServerId -> 删行，审计记 state=unknown（没有目标可写），计 unknown
 *        · 解析不了且 Shittim 账号列表也读不到 -> **保留行**，计 held
 *          （服务器不可达时"判定不了"不等于"没有目标"，此时盲删就是在造新的孤儿封禁）
 *   ③ 卡密 / 设备行：只删行，**绝不碰** MySQL cards.status / device_ban.txt
 *      （限时封禁本来就没写那两个；永久行不在本次清理范围）
 *   ④ **先写审计，再 DELETE**：DELETE 失败时至少知道原本要删什么
 *   ⑤ 按 id 分批 DELETE（只删"扫到且确认可删"的 id），每条都重新核对 until_epoch <= now
 *
 * 全程 try/except：不抛异常，失败返回 array('ok'=>false,'error'=>'人话')。
 *
 * @return array('ok'=>bool,'error'=>string,'deleted'=>int,'released'=>int,'failed'=>int,
 *               'unknown'=>int,'held'=>int,'deferred'=>int,'planned'=>int,
 *               'notes'=>array,'detail'=>string)
 */
function banexp_purge_expired()
{
    $out = array(
        'ok' => false, 'error' => '', 'deleted' => 0, 'released' => 0,
        'failed' => 0, 'unknown' => 0, 'held' => 0, 'deferred' => 0,
        'planned' => 0, 'notes' => array(), 'detail' => '',
    );

    try {
        if (!banexp_ensure_schema()) {
            $out['error'] = '封禁表不可用：' . banexp_db_path();
            return $out;
        }

        /* --- ① 查出所有到期行（永久行 until_epoch IS NULL，天然被排除） --- */
        $all = banexp_all(true);
        if (empty($all['ok'])) {
            $out['error'] = (string)$all['error'];
            return $out;
        }
        $now = time();
        $due = array();
        foreach ($all['rows'] as $row) {
            if ($row['until_epoch'] === null) {
                continue;
            }
            if ((int)$row['until_epoch'] > $now) {
                continue;
            }
            $due[] = $row;
        }
        if (!$due) {
            $out['ok']     = true;
            $out['detail'] = '没有到期的行，什么都没做';
            return $out;
        }

        $log     = array();   /* 审计明细：一行一条 */
        $protect = array();   /* 这些 id 的到期行**不删**（还原失败 / 判定不了 / 超单次上限） */

        /* --- ② 账号行先还原 State（卡密/设备行只登记，不动旧机制） --- */
        foreach ($due as $row) {
            $id   = (int)$row['id'];
            $kind = (string)$row['kind'];
            $tgt  = (string)$row['target'];

            if ($kind !== 'account') {
                $log[] = $kind . ' ' . banexp_cut($tgt, 40) . ' => 只删行（不碰 cards.status / device_ban.txt）row #' . $id;
                continue;
            }

            if ($out['released'] + $out['failed'] >= (int)BANEXP_PURGE_MAX_RELEASE) {
                $out['deferred']++;
                $protect[$id] = true;
                $log[] = 'account ' . banexp_cut($tgt, 40) . ' => 超出单次上限，保留到下次 row #' . $id;
                continue;
            }

            $pub = (int)$tgt;
            if ($pub <= 0) {
                $out['unknown']++;
                $log[] = 'account ' . banexp_cut($tgt, 40) . ' => state=unknown（target 不是数字 publisher）仍删行 row #' . $id;
                continue;
            }

            $rs  = banexp_purge_resolve_sid($pub);
            $sid = (int)$rs['server_id'];
            if ($sid <= 0) {
                if (empty($rs['index_ok'])) {
                    /* 服务器不可达 / Admin Key 不对：判定不了目标 = 不能盲删，保留到下次 */
                    $out['held']++;
                    $protect[$id] = true;
                    $log[] = 'account ' . $tgt . ' => state=unknown（publisher ' . $pub
                        . '：accounts.db 没有 shittim_server_id，Shittim 账号列表也读不到，无法判定）行保留 row #' . $id;
                    continue;
                }
                $out['unknown']++;
                $log[] = 'account ' . $tgt . ' => state=unknown（publisher ' . $pub
                    . '：accounts.db 的 shittim_server_id 为 NULL/无行，Shittim 里也反查不到）仍删行 row #' . $id;
                continue;
            }

            /* 这一步等价于 ba_account_update($sid, array('State' => 1))，与 sweep 走同一条路 */
            $rc = ban_account_toggle($sid, false);
            if (empty($rc['ok'])) {
                $out['failed']++;
                $protect[$id] = true;
                $log[] = 'account ' . $tgt . ' => state=fail（ServerId ' . $sid . '：'
                    . banexp_cut((string)$rc['error'], 80) . '）行保留 row #' . $id;
                continue;
            }
            $out['released']++;
            $log[] = 'account ' . $tgt . ' => state=ok（ServerId ' . $sid . '，解析来源 ' . $rs['source'] . '）row #' . $id;
        }

        /* 待删除的 id = 到期行 - 受保护行（failed / held / deferred）。
           只删"扫到并确认过"的 id，不用 NOT IN 反选：
             · 不会把本次扫描之后才出现的到期行顺手删掉（那种行没做过 State 还原）；
             · 不受 SQLite 的 SQL 变量数上限约束（分批 400 个一批）。 */
        $delIds = array();
        foreach ($due as $row) {
            $rid = (int)$row['id'];
            if (!isset($protect[$rid])) {
                $delIds[] = $rid;
            }
        }
        $out['planned'] = count($delIds);

        /* --- ③ 先写审计，再删行（顺序不能反：DELETE 失败也要留痕） --- */
        if (function_exists('audit_log')) {
            try {
                audit_log(
                    'ban.purge',
                    'bans 到期 ' . count($due) . ' 行 / 计划删 ' . (int)$out['planned'] . ' 行',
                    '清理到期封禁行（先还原 State 再删行）'
                    . ' | 到期 ' . count($due) . ' 行'
                    . ' | 计划删行 ' . (int)$out['planned']
                    . ' | State 复原：成功 ' . (int)$out['released']
                    . ' / 失败 ' . (int)$out['failed']
                    . ' / 未知已删行 ' . (int)$out['unknown']
                    . ' / 未知保留行 ' . (int)$out['held']
                    . ' | 卡密与设备只删行（不动 cards.status / device_ban.txt）'
                    . ((int)$out['deferred'] > 0 ? (' | 超单次上限顺延 ' . (int)$out['deferred'] . ' 行') : '')
                    . ' | 明细：' . implode('；', array_slice($log, 0, 80))
                );
            } catch (Throwable $e) {
                $out['notes'][] = '审计写入异常（已忽略）：' . $e->getMessage();
            }
        } else {
            $out['notes'][] = '面板没有 audit_log()，本次没有写审计';
        }

        /* --- ④ 删行：按 id 分批（400/批），每条都重新核对 until_epoch <= now --- */
        $pdo = banexp_pdo();
        if (!$pdo) {
            $out['error'] = 'PHP 没有 pdo_sqlite，写不了封禁表（State 已按②处理，行未删）';
            return $out;
        }
        $deleted = 0;
        foreach (array_chunk($delIds, 400) as $chunk) {
            $ph   = array();
            $args = array(time());
            foreach ($chunk as $rid) {
                $ph[]   = '?';
                $args[] = (int)$rid;
            }
            $sql = 'DELETE FROM `bans`'
                . ' WHERE `until_epoch` IS NOT NULL AND `until_epoch` <= ?'
                . ' AND `id` IN (' . implode(', ', $ph) . ')';
            $st = $pdo->prepare($sql);
            $st->execute($args);
            $deleted += (int)$st->rowCount();
        }
        $out['deleted'] = $deleted;
        $out['ok']      = true;

        $out['detail'] = '到期 ' . count($due) . ' 行：删行 ' . (int)$out['deleted']
            . '，State 复原 ' . (int)$out['released']
            . '，保留 ' . count($protect) . ' 行';

        if ((int)$out['failed'] > 0) {
            $out['notes'][] = (int)$out['failed']
                . ' 个账号的 State 没还原成功，它们的封禁行「没有删」，再点一次会重试';
        }
        if ((int)$out['held'] > 0) {
            $out['notes'][] = (int)$out['held']
                . ' 个账号行判定不了目标（Shittim 账号列表读不到），已保留、未删';
        }
        if ((int)$out['unknown'] > 0) {
            $out['notes'][] = (int)$out['unknown']
                . ' 个账号行解析不到 Shittim ServerId（审计里记 state=unknown），只删了行、没写 State';
        }

        banexp_all(true);
        return $out;
    } catch (Throwable $e) {
        $out['ok']    = false;
        $out['error'] = '清理到期行失败：' . $e->getMessage()
            . '（已还原的 State 不会回滚；还原失败的行原样保留）';
        return $out;
    }
}

/* -------------------------------------------------------------- 5.4 时长选择 --- */

/**
 * 封禁时长选项（页面下拉框）
 * @return array value => label
 */
function banexp_duration_options()
{
    return array(
        'perm'   => '永久（默认）',
        '1h'     => '1 小时',
        '1d'     => '1 天',
        '7d'     => '7 天',
        '30d'    => '30 天',
        'custom' => '自定义（选到具体时间点）',
    );
}

/** @return array value => 秒 */
function banexp_duration_seconds()
{
    return array('1h' => 3600, '1d' => 86400, '7d' => 604800, '30d' => 2592000);
}

/**
 * 截断（不依赖 helpers.php 的 str_limit，单文件也安全）
 * @param string $s
 * @param int    $n
 * @return string
 */
function banexp_cut($s, $n)
{
    $s = (string)$s;
    $n = (int)$n;
    if ($n <= 0) {
        return '';
    }
    if (function_exists('mb_strlen') && function_exists('mb_substr')) {
        if (mb_strlen($s, 'UTF-8') <= $n) {
            return $s;
        }
        return mb_substr($s, 0, $n, 'UTF-8') . '…';
    }
    if (strlen($s) <= $n) {
        return $s;
    }
    return substr($s, 0, $n) . '…';
}

/**
 * 卡密打码（不依赖 helpers.php 的 mask_card）
 * @param string $key
 * @return string
 */
function banexp_mask_card($key)
{
    if (function_exists('mask_card')) {
        return mask_card($key);
    }
    $s = (string)$key;
    if ($s === '') {
        return '（空）';
    }
    if (strlen($s) <= 8) {
        return str_repeat('*', strlen($s));
    }
    return substr($s, 0, 4) . '****' . substr($s, -4);
}

/** POST 取字符串（不依赖 helpers，独立可用） */
function banexp_post_str($k, $d = '')
{
    if (isset($_POST[$k]) && is_string($_POST[$k])) {
        return trim($_POST[$k]);
    }
    if (isset($_POST[$k]) && is_scalar($_POST[$k])) {
        return trim((string)$_POST[$k]);
    }
    return $d;
}

/**
 * 从 POST 里算 until_epoch（服务器时间 + 时长，或自定义时间点）
 *
 * POST 字段：duration = perm|1h|1d|7d|30d|custom，until_local = 'Y-m-d\TH:i'（datetime-local）
 *
 * @return array('ok'=>bool,'error'=>string,'until'=>int|null,'duration'=>string,'label'=>string)
 */
function banexp_until_from_post()
{
    $out = array('ok' => true, 'error' => '', 'until' => null, 'duration' => 'perm', 'label' => '永久');
    $d   = banexp_post_str('duration', 'perm');
    if ($d === '') {
        $d = 'perm';
    }
    $opts = banexp_duration_options();
    if (!isset($opts[$d])) {
        $out['ok']    = false;
        $out['error'] = '时长选项无效：' . banexp_cut($d, 20);
        return $out;
    }
    $out['duration'] = $d;
    $out['label']    = $opts[$d];
    if ($d === 'perm') {
        $out['until'] = null;
        $out['label'] = '永久';
        return $out;
    }
    $now = time();
    if ($d !== 'custom') {
        $secs = banexp_duration_seconds();
        if (!isset($secs[$d])) {
            $out['ok']    = false;
            $out['error'] = '时长选项无效：' . $d;
            return $out;
        }
        $out['until'] = $now + (int)$secs[$d];
        return $out;
    }

    /* 自定义：datetime-local 是 'Y-m-d\TH:i'（有些浏览器带秒），一律按 Asia/Shanghai 解释 */
    $s = banexp_post_str('until_local', '');
    if ($s === '') {
        $out['ok']    = false;
        $out['error'] = '选了「自定义」但没填时间点';
        return $out;
    }
    $s  = str_replace('T', ' ', $s);
    $s  = trim($s);
    $dt = false;
    foreach (array('Y-m-d H:i:s', 'Y-m-d H:i') as $fmt) {
        $dt = DateTime::createFromFormat($fmt, $s, new DateTimeZone(BANEXP_TZ));
        if ($dt instanceof DateTime) {
            $err = DateTime::getLastErrors();
            if (is_array($err) && ((int)$err['warning_count'] > 0 || (int)$err['error_count'] > 0)) {
                $dt = false;
            }
            if ($dt instanceof DateTime) {
                break;
            }
        }
    }
    if (!($dt instanceof DateTime)) {
        $out['ok']    = false;
        $out['error'] = '自定义时间点格式不对（要 2026-11-20 20:00 这种）：' . banexp_cut($s, 32);
        return $out;
    }
    $ts = (int)$dt->getTimestamp();
    if ($ts <= $now) {
        $out['ok']    = false;
        $out['error'] = '自定义时间点必须晚于当前时间（当前 ' . date('Y-m-d H:i') . '，填的是 ' . ban_msg_time($ts) . '）';
        return $out;
    }
    if ($ts - $now > 3650 * 86400) {
        $out['ok']    = false;
        $out['error'] = '时长超过 10 年，拒绝（要永久请选「永久」）';
        return $out;
    }
    $out['until'] = $ts;
    $out['label'] = '自定义至 ' . ban_msg_time($ts);
    return $out;
}

/* ------------------------------------------------------------ 5.5 三维度写 --- */

/**
 * 账号封禁 / 解封：bans 表 + Shittim State（两个维度互不影响，本函数只碰账号）
 *
 * @param int      $serverId
 * @param int      $publisherId  accounts.publisher_account_id（0 = 未知）
 * @param bool     $on
 * @param int|null $untilEpoch   null = 永久
 * @param string   $reason
 * @param string   $by
 * @return array
 */
function banexp_toggle_account($serverId, $publisherId, $on, $untilEpoch, $reason = '', $by = '')
{
    $serverId    = (int)$serverId;
    $publisherId = (int)$publisherId;
    $out = array(
        'ok' => false, 'error' => '', 'notice' => '', 'warnings' => array(),
        'server_id' => $serverId, 'publisher_id' => $publisherId,
        'until_epoch' => null, 'table_ok' => false, 'legacy_ok' => false,
    );
    if ($serverId <= 0) {
        $out['error'] = 'ServerId 无效';
        return $out;
    }
    if (!$on) {
        $untilEpoch = null;
    }

    /* --- ① bans 表（永久与限时都写；这是文案与"限时"的唯一事实源） --- */
    if ($publisherId > 0) {
        $rt = $on
            ? banexp_upsert('account', (string)$publisherId, $untilEpoch, $reason, $by)
            : banexp_clear('account', (string)$publisherId);
        $out['table_ok'] = !empty($rt['ok']);
        if (!$out['table_ok']) {
            $out['warnings'][] = '封禁表写入失败：' . $rt['error'];
        }
    } else {
        $out['warnings'][] = '该账号读不到 publisherAccountId，封禁表没写：SDK 侧不会弹封禁文案'
            . '（Shittim State 仍然生效，玩家进不去，但看到的是客户端自己的报错）。';
    }

    /* --- ② Shittim State（永久=长期拦截；限时也写，保证拦得住；到期由读侧还原） --- */
    $rs = ban_account_toggle($serverId, $on);
    $out['legacy_ok'] = !empty($rs['ok']);
    if (!$out['legacy_ok']) {
        $out['warnings'][] = 'Shittim State 写入失败：' . $rs['error'];
    }
    $out['until_epoch'] = $untilEpoch;

    $out['ok'] = ($out['table_ok'] || $out['legacy_ok']);
    if (!$out['ok']) {
        $out['error'] = implode('；', $out['warnings']);
        return $out;
    }

    $when = ($untilEpoch === null) ? '永久' : ('至 ' . ban_msg_time($untilEpoch) . '（到期自动解除）');
    $out['notice'] = '账号 ' . $serverId . ($on ? (' 已封禁：' . $when) : ' 已解封')
        . '。封禁表 ' . ($out['table_ok'] ? 'ok' : '未写')
        . '，Shittim State ' . ($out['legacy_ok'] ? ($on ? '=2 Dormant' : '=1 Normal') : '未改')
        . '。本次没有动卡密和设备。';
    return $out;
}

/**
 * 卡密封禁 / 解封：bans 表 + cards.status（限时**不改** status，见文件头 5 的说明）
 *
 * @param int      $cardId
 * @param string   $cardKey
 * @param bool     $on
 * @param int|null $untilEpoch
 * @param string   $reason
 * @param string   $by
 * @return array
 */
function banexp_toggle_card($cardId, $cardKey, $on, $untilEpoch, $reason = '', $by = '')
{
    $cardId  = (int)$cardId;
    $cardKey = trim((string)$cardKey);
    $out = array(
        'ok' => false, 'error' => '', 'notice' => '', 'warnings' => array(),
        'card_id' => $cardId, 'card_key' => $cardKey, 'until_epoch' => null,
        'table_ok' => false, 'legacy_ok' => false, 'legacy_touched' => false,
        'bancard' => array(),
    );
    if ($cardId <= 0 && $cardKey === '') {
        $out['error'] = '卡密参数无效';
        return $out;
    }
    if (!$on) {
        $untilEpoch = null;
    }
    $out['until_epoch'] = $untilEpoch;

    /* --- ① bans 表 --- */
    if ($cardKey !== '') {
        $rt = $on
            ? banexp_upsert('card', $cardKey, $untilEpoch, $reason, $by)
            : banexp_clear('card', $cardKey);
        $out['table_ok'] = !empty($rt['ok']);
        if (!$out['table_ok']) {
            $out['warnings'][] = '封禁表写入失败：' . $rt['error'];
        }
    } else {
        $out['warnings'][] = '这张卡读不到 card_key，封禁表没写（只有 MySQL status 生效）。';
    }

    /* --- ② cards.status：永久写；限时**不写**（否则到期后 sync 不会再导出这张卡） ---
     * 限时时反而要把可能残留的 disabled 归位成 active：否则以前永久禁用的卡
     * 改成限时封禁后永远不会恢复。 */
    $isPerm = ($untilEpoch === null);
    if ($on && !$isPerm) {
        $out['legacy_ok'] = true;   /* 限时只用封禁表，SDK 读取侧判定 */
        if ($cardId > 0) {
            /* [GATEFIX] 护栏：这条路径自己会带 until 写账号封禁行，别让 ban_card_toggle 再写一遍 */
            bancard_sync_guard_push();
            try {
                $rst = ban_card_toggle($cardId, false);
            } finally {
                bancard_sync_guard_pop();
            }
            $out['legacy_ok'] = !empty($rst['ok']);
            if (empty($rst['ok'])) {
                $out['warnings'][] = '把 cards.status 归位成 active 失败：' . $rst['error'];
            }
        }
    } else {
        if ($cardId > 0) {
            bancard_sync_guard_push();
            try {
                $rc = ban_card_toggle($cardId, $on);
            } finally {
                bancard_sync_guard_pop();
            }
            $out['legacy_ok'] = !empty($rc['ok']);
            $out['legacy_touched'] = $out['legacy_ok'];
            if (!$out['legacy_ok']) {
                $out['warnings'][] = 'cards.status 写入失败：' . $rc['error'];
            }
        } else {
            $out['warnings'][] = '没有卡片 id，cards.status 未改。';
        }
    }

    /* --- ③ [GATEFIX] 账号封禁行：把"卡密维度"映射成桥认的 publisher 账号行 ---
     * 限时 / 永久与卡密那条完全一致（同一个 $untilEpoch）；解封只删 reason 以「卡密封禁」开头的行。
     * 这一步是**独立**的：它失败不会让卡密行回滚，也不会把玩家误封（NOTES.md §4）。 */
    if ($cardKey !== '') {
        $map = bancard_account_apply($cardKey, (bool)$on, $on ? $untilEpoch : null, (string)$by);
        $out['bancard'] = $map;
        if (empty($map['ok'])) {
            $out['warnings'][] = '账号封禁行（游戏层拦截）没写成功：' . $map['error']
                . '（玩家仍然能进游戏，不会误封；请再点一次或到封禁页手动处理）';
            bancard_audit('card.ban_account_fail', $cardKey,
                '卡密封禁(' . ($on ? '封' : '解') . ')映射失败：' . $map['error']);
        } elseif (!empty($map['warning'])) {
            $out['warnings'][] = $map['warning'];
        }
    } else {
        $out['warnings'][] = '这张卡读不到 card_key，账号封禁行没写：游戏层拦不到'
            . '（SDK 也不再拦卡密维度，见 NOTES.md §3）；请检查卡密数据后重试';
    }

    $out['ok'] = ($out['table_ok'] || $out['legacy_ok']);
    if (!$out['ok']) {
        $out['error'] = implode('；', $out['warnings']);
        return $out;
    }

    /* [GATEFIX] 把"账号维度那一步"的结果说清楚，运营才知道游戏层到底会不会拦 */
    $bm   = (isset($out['bancard']) && is_array($out['bancard'])) ? $out['bancard'] : array();
    $bmsg = '';
    $bact = isset($bm['action']) ? (string)$bm['action'] : '';
    if (!empty($bm['ok']) && $bact === 'deleted') {
        $bmsg = ' 账号维度：publisher ' . (int)$bm['pub'] . ' 的卡密封禁映射行已删。';
    } elseif (!empty($bm['ok']) && $bact === 'skip-free') {
        $bmsg = ' 账号维度：公益卡不做 publisher 映射（封禁仍由 SDK 层拦）。';
    } elseif (!empty($bm['ok']) && $bact === 'keep-manual') {
        $bmsg = ' 账号维度：该 publisher 已有手工账号封禁，未覆盖它。';
    } elseif (!empty($bm['ok']) && ($bact === 'added' || $bact === 'updated')) {
        $bmsg = ' 账号维度（游戏层拦截）：publisher ' . (int)$bm['pub'] . ' 的映射行'
            . ($bact === 'added' ? '已写入' : '已更新')
            . '（until=' . ($bm['until_epoch'] === null ? '永久' : ban_msg_time((int)$bm['until_epoch'])) . '）'
            . '，桥会回官方封禁包（ErrorCode 1025 + BanReason）。';
    } elseif (empty($bm['ok']) && $bact === 'error') {
        $bmsg = ' ⚠ 账号维度映射没写成功（玩家仍然能进游戏，不会误封），详见警告。';
    }

    if (!$on) {
        $out['notice'] = '卡密 ' . banexp_mask_card($cardKey) . ' 已解封（封禁行已删，cards.status 已回 active）。' . $bmsg;
        return $out;
    }
    if ($isPerm) {
        $out['notice'] = '卡密 ' . banexp_mask_card($cardKey) . ' 已永久禁用：封禁表 + cards.status=disabled（≤60 秒同步到 cards.json）。' . $bmsg;
    } else {
        $out['notice'] = '卡密 ' . banexp_mask_card($cardKey) . ' 已限时封禁至 ' . ban_msg_time($untilEpoch)
            . '：只写封禁表（不动 cards.status，这样到期后这张卡自动恢复可用，不用人工处理）。' . $bmsg;
    }
    return $out;
}

/**
 * 设备封禁 / 解封：bans 表 + device_ban.txt（限时**不写**文件，理由同上）
 *
 * @param string   $dev
 * @param bool     $on
 * @param int|null $untilEpoch
 * @param string   $reason
 * @param string   $by
 * @return array
 */
function banexp_toggle_device($dev, $on, $untilEpoch, $reason = '', $by = '')
{
    $dev = trim((string)$dev);
    $out = array(
        'ok' => false, 'error' => '', 'notice' => '', 'warnings' => array(),
        'device' => $dev, 'until_epoch' => null,
        'table_ok' => false, 'legacy_ok' => false, 'changed' => false, 'count' => 0,
    );
    if ($dev === '') {
        $out['error'] = '设备号为空';
        return $out;
    }
    if (!$on) {
        $untilEpoch = null;
    }
    $out['until_epoch'] = $untilEpoch;

    /* --- ① bans 表 --- */
    $rt = $on
        ? banexp_upsert('device', $dev, $untilEpoch, $reason, $by)
        : banexp_clear('device', $dev);
    $out['table_ok'] = !empty($rt['ok']);
    if (!$out['table_ok']) {
        $out['warnings'][] = '封禁表写入失败：' . $rt['error'];
    }

    /* --- ② device_ban.txt：永久写；限时**不写** ---
     * 限时时反而要把可能残留的黑名单行删掉：否则"先永久封、再改限时"之后，
     * 文件里那一行不会自己过期，会把设备永久锁死。 */
    $isPerm = ($untilEpoch === null);
    if ($on && !$isPerm) {
        $out['legacy_ok'] = true;
        $rdel = ban_device_set($dev, false);
        if (empty($rdel['ok'])) {
            $out['warnings'][] = '删除 device_ban.txt 里的残留行失败：' . $rdel['error'];
        } elseif (!empty($rdel['changed'])) {
            $out['changed'] = true;
        }
    } else {
        $rd = ban_device_set($dev, $on);
        $out['legacy_ok'] = !empty($rd['ok']);
        $out['changed']   = !empty($rd['changed']);
        $out['count']     = isset($rd['count']) ? (int)$rd['count'] : 0;
        if (!$out['legacy_ok']) {
            $out['warnings'][] = 'device_ban.txt 写入失败：' . $rd['error'];
        }
    }

    $out['ok'] = ($out['table_ok'] || $out['legacy_ok']);
    if (!$out['ok']) {
        $out['error'] = implode('；', $out['warnings']);
        return $out;
    }

    if (!$on) {
        $out['notice'] = '设备 ' . banexp_cut($dev, 40) . ' 已解封（封禁行已删，黑名单文件里若有也一并移除）。';
        return $out;
    }
    if ($isPerm) {
        $out['notice'] = '设备 ' . banexp_cut($dev, 40) . ' 已永久封禁（封禁表 + device_ban.txt 双写，当前文件 '
            . (int)$out['count'] . ' 条）。';
    } else {
        $out['notice'] = '设备 ' . banexp_cut($dev, 40) . ' 已限时封禁至 ' . ban_msg_time($untilEpoch)
            . '：只写封禁表（不写 device_ban.txt，到期自动解除，不用人工删行）。';
    }
    return $out;
}

/* ------------------------------------------------------- 5.6 到期自愈（账号） --- */

/**
 * 账号维度专用：把「已到期的封禁行」对应的 Shittim State 还原成 1，然后删行。
 *
 * Shittim 的 State=2 不会自己过期；限时账号封禁到期后必须有谁把它改回 1。
 * 桥（account_auth_probe.py 的 BAPATCH-BANEXP v1）在每次账号鉴权前会做同一件事，
 * 这里是**第二张网**：只要运维打开一次封禁页，过期账号就当场恢复。
 *
 * @param int $max 单次最多处理多少行（避免页面卡住）
 * @return array('ok'=>bool,'error'=>string,'released'=>int,'failed'=>int,'checked'=>int,'notes'=>array)
 */
function banexp_sweep_account_releases($max = 20)
{
    $out = array('ok' => true, 'error' => '', 'released' => 0, 'failed' => 0, 'checked' => 0, 'notes' => array());
    $all = banexp_all();
    if (!$all['ok']) {
        $out['ok']    = false;
        $out['error'] = $all['error'];
        return $out;
    }
    $due = array();
    $now = time();
    foreach ($all['rows'] as $row) {
        if ($row['kind'] !== 'account') {
            continue;
        }
        if ($row['until_epoch'] === null || (int)$row['until_epoch'] > $now) {
            continue;
        }
        $due[] = $row;
        if (count($due) >= (int)$max) {
            break;
        }
    }
    if (!$due) {
        return $out;
    }

    $idx = ban_accounts_index();
    $pub2sid = array();
    if ($idx['ok']) {
        foreach ($idx['rows'] as $sid => $a) {
            $p = isset($a['publisherAccountId']) ? (int)$a['publisherAccountId'] : 0;
            if ($p > 0) {
                $pub2sid[$p] = (int)$sid;
            }
        }
    } else {
        $out['notes'][] = 'Shittim 账号列表读不到（' . $idx['error'] . '），账号到期自愈全部跳过。';
        return $out;
    }

    foreach ($due as $row) {
        $out['checked']++;
        $pub = (int)$row['target'];
        $sid = isset($pub2sid[$pub]) ? (int)$pub2sid[$pub] : 0;
        if ($sid <= 0) {
            $out['notes'][] = '封禁行 #' . $row['id'] . '（publisher ' . $pub . '）在 Shittim 里找不到账号，跳过。';
            continue;
        }
        $state = isset($idx['rows'][$sid]['state']) ? (string)$idx['rows'][$sid]['state'] : '';
        $banned = function_exists('player_is_banned')
            ? player_is_banned($state)
            : (strcasecmp($state, 'Dormant') === 0);
        if ($banned) {
            $r = ban_account_toggle($sid, false);
            if (empty($r['ok'])) {
                $out['failed']++;
                $out['notes'][] = '账号 ' . $sid . '（publisher ' . $pub . '）还原 State=1 失败：' . $r['error'];
                continue;
            }
            if (function_exists('audit_log')) {
                audit_log('ban.account_auto_release', 'ServerId ' . $sid,
                    '限时封禁到期自动解封 | publisher ' . $pub
                    . ' | until ' . ban_msg_time((int)$row['until_epoch'])
                    . ' | 封禁行 #' . $row['id'] . ' 已删（面板 sweep）');
            }
        }
        $rc = banexp_clear('account', (string)$pub);
        if (!empty($rc['ok'])) {
            $out['released']++;
        } else {
            $out['failed']++;
            $out['notes'][] = '账号 ' . $sid . ' 的封禁行删除失败：' . $rc['error'];
        }
    }
    $out['ok'] = ($out['failed'] === 0);
    return $out;
}

/* ------------------------------------------------------------- 5.7 聚合查询 --- */

/**
 * 按维度取行（页面渲染用）
 * @param string $kind
 * @param bool   $reload
 * @return array
 */
function banexp_rows_of_kind($kind, $reload = false)
{
    $out = array();
    $all = banexp_all($reload);
    foreach ($all['rows'] as $row) {
        if ($row['kind'] === $kind) {
            $out[] = $row;
        }
    }
    usort($out, 'banexp_cmp_row');
    return $out;
}

/** 排序：封禁中优先，到期时间近的优先，永久排最后 */
function banexp_cmp_row($a, $b)
{
    $aa = banexp_is_active($a);
    $ba = banexp_is_active($b);
    if ($aa !== $ba) {
        return $aa ? -1 : 1;
    }
    $au = ($a['until_epoch'] === null) ? PHP_INT_MAX : (int)$a['until_epoch'];
    $bu = ($b['until_epoch'] === null) ? PHP_INT_MAX : (int)$b['until_epoch'];
    if ($au === $bu) {
        return ((int)$a['id'] < (int)$b['id']) ? -1 : 1;
    }
    return ($au < $bu) ? -1 : 1;
}

/**
 * 三个维度的封禁表计数（页面统计卡用）
 * @return array('ok'=>bool,'error'=>string,'path'=>string,'account'=>array,'card'=>array,'device'=>array,'total'=>int)
 */
function banexp_summary()
{
    $out = array(
        'ok' => true, 'error' => '', 'path' => banexp_db_path(), 'total' => 0,
        'account' => array('active' => 0, 'expired' => 0, 'perm' => 0),
        'card'    => array('active' => 0, 'expired' => 0, 'perm' => 0),
        'device'  => array('active' => 0, 'expired' => 0, 'perm' => 0),
    );
    $all = banexp_all();
    if (!$all['ok']) {
        $out['ok']    = false;
        $out['error'] = $all['error'];
        return $out;
    }
    foreach ($all['rows'] as $row) {
        $k = $row['kind'];
        if (!isset($out[$k])) {
            continue;
        }
        $out['total']++;
        if (banexp_is_active($row)) {
            $out[$k]['active']++;
            if ($row['until_epoch'] === null) {
                $out[$k]['perm']++;
            }
        } else {
            $out[$k]['expired']++;
        }
    }
    return $out;
}

/**
 * 「孤儿封禁」只读探测：Shittim 侧 State=2(Dormant)，但 bans 表里没有任何
 * kind='account' 的对应行（按 publisher 对）。
 *
 * 为什么会发生：2026-11-18 之前的「清理已到期」只删 bans 行、不还原 State。
 * 行一旦被删，桥和本页 sweep 都再没有线索（两边都靠 bans 行定位目标），
 * 账号就永久 Dormant，两端都不会再碰它。
 *
 * 数据源全部复用现成的读侧函数，**不新写 SQL**、不改任何数据（本函数连写都不做）：
 *   · player_bridge_accounts() —— 桥接 accounts.db 的 accounts 表（只读、进程内已缓存）；
 *                                 只有 shittim_server_id 不为 NULL 的账号才参与判断
 *   · ban_accounts_index()     —— Shittim /api/admin/accounts（进程内已缓存）
 *   · banexp_all()             —— bans 表（进程内已缓存）
 * 这三份数据在封禁页上本来就已经读过，所以**全量扫描不产生额外 API 调用**。
 *
 * 判定用的对应关系：bridge 行的 publisher_account_id ←→ bans(kind='account', target=publisher)。
 *
 * @param int $maxList 最多带回多少个样本（页面只展示前几个）
 * @return array('ok'=>bool,'error'=>string,'count'=>int,'sids'=>array,'checked'=>int,'skipped'=>string)
 */
function banexp_orphan_accounts($maxList = 12)
{
    $out = array('ok' => false, 'error' => '', 'count' => 0, 'sids' => array(),
        'checked' => 0, 'skipped' => '');
    try {
        $all = banexp_all();
        if (empty($all['ok'])) {
            $out['error'] = (string)$all['error'];
            return $out;
        }
        if (!function_exists('player_bridge_accounts')) {
            $out['skipped'] = '面板没有 player_bridge_accounts()，跳过孤儿检测';
            return $out;
        }
        $idx = ban_accounts_index();
        if (empty($idx['ok'])) {
            $out['error'] = (string)$idx['error'];
            return $out;
        }
        $bridge = player_bridge_accounts();
        if (!$bridge) {
            $out['skipped'] = '桥接 accounts.db 读不到或为空，跳过孤儿检测';
            return $out;
        }

        $hasCol = false;
        $pub2sid = array();   /* publisher(归一为 int 字符串) => ServerId */
        foreach ($bridge as $pk => $brow) {
            if (!is_array($brow) || !array_key_exists('shittim_server_id', $brow)) {
                continue;
            }
            $hasCol = true;
            $pub = (int)$pk;
            $sid = (int)$brow['shittim_server_id'];
            if ($pub > 0 && $sid > 0) {
                $pub2sid[(string)$pub] = $sid;
            }
        }
        if (!$hasCol) {
            $out['skipped'] = '桥接 accounts.db 没有 shittim_server_id 列（老库未迁移），跳过孤儿检测';
            return $out;
        }

        foreach ($pub2sid as $pubStr => $sid) {
            $out['checked']++;
            if (!isset($idx['rows'][$sid])) {
                continue;                        /* Shittim 里已经没有这个账号 */
            }
            $state = isset($idx['rows'][$sid]['state']) ? (string)$idx['rows'][$sid]['state'] : '';
            $banned = function_exists('player_is_banned')
                ? player_is_banned($state)
                : (strcasecmp($state, 'Dormant') === 0);
            if (!$banned) {
                continue;
            }
            if (banexp_row('account', $pubStr) !== null) {
                continue;                        /* 有封禁记录（含已到期未清的），不算孤儿 */
            }
            $out['count']++;
            if (count($out['sids']) < (int)$maxList) {
                $out['sids'][] = array(
                    'server_id' => (int)$sid,
                    'publisher' => (int)$pubStr,
                    'nickname'  => isset($idx['rows'][$sid]['nickname'])
                        ? (string)$idx['rows'][$sid]['nickname'] : '',
                    'state'     => $state,
                );
            }
        }
        $out['ok'] = true;
        return $out;
    } catch (Throwable $e) {
        $out['ok']    = false;
        $out['error'] = '孤儿封禁检测失败：' . $e->getMessage();
        return $out;
    }
}

/**
 * 页面单元格用：一次拿到某玩家账号维度的封禁行
 * @param int $publisherId
 * @return array|null
 */
function banexp_account_row($publisherId)
{
    $pub = (int)$publisherId;
    if ($pub <= 0) {
        return null;
    }
    return banexp_row('account', (string)$pub);
}

/**
 * 页面单元格用：一张卡的封禁行
 * @param string $cardKey
 * @return array|null
 */
function banexp_card_row($cardKey)
{
    $key = trim((string)$cardKey);
    if ($key === '') {
        return null;
    }
    return banexp_row('card', $key);
}

/**
 * 页面单元格用：一台设备的封禁行
 * @param string $dev
 * @return array|null
 */
function banexp_device_row($dev)
{
    $dev = trim((string)$dev);
    if ($dev === '') {
        return null;
    }
    return banexp_row('device', $dev);
}
