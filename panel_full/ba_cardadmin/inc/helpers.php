<?php
/**
 * inc/helpers.php — 通用工具：输出转义、URL、布局、设置、分页、时间
 *
 * 本文件不依赖登录状态，install.php 也会 require 它。
 */

if (!defined('CARDADMIN')) {
    http_response_code(403);
    exit('403 Forbidden');
}

require_once __DIR__ . '/db.php';

/* -------------------------------------------------------------- 输出转义 --- */

/** HTML 转义（所有输出一律过这个函数） */
function e($v)
{
    return htmlspecialchars((string)$v, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

/** htmlspecialchars 的短别名 */
function h($v)
{
    return e($v);
}

/** 安全取 GET */
function get_q($k, $d = '')
{
    if (!isset($_GET[$k])) {
        return $d;
    }
    return is_string($_GET[$k]) ? $_GET[$k] : $d;
}

/** 安全取 POST（字符串） */
function post_q($k, $d = '')
{
    if (!isset($_POST[$k])) {
        return $d;
    }
    return is_string($_POST[$k]) ? $_POST[$k] : $d;
}

/** 取整数：GET */
function get_int($k, $d = 0, $min = null, $max = null)
{
    $v = isset($_GET[$k]) ? (int)$_GET[$k] : (int)$d;
    return clamp_int($v, $min, $max);
}

/** 取整数：POST */
function post_int($k, $d = 0, $min = null, $max = null)
{
    $v = isset($_POST[$k]) ? (int)$_POST[$k] : (int)$d;
    return clamp_int($v, $min, $max);
}

function clamp_int($v, $min = null, $max = null)
{
    $v = (int)$v;
    if ($min !== null && $v < $min) {
        $v = $min;
    }
    if ($max !== null && $v > $max) {
        $v = $max;
    }
    return $v;
}

/* ------------------------------------------------------------------ URL --- */

/** 站点根路径（兼容子目录部署） */
function app_base()
{
    static $base = null;
    if ($base !== null) {
        return $base;
    }
    if (defined('APP_BASE') && APP_BASE !== '') {
        $base = '/' . trim(APP_BASE, '/') . '/';
        if ($base === '//') {
            $base = '/';
        }
        return $base;
    }
    $script = isset($_SERVER['SCRIPT_NAME']) ? str_replace('\\', '/', (string)$_SERVER['SCRIPT_NAME']) : '/index.php';
    /* dirname() 在 Windows 上会返回反斜杠，统一成正斜杠（线上是 Linux，这里只是保持可移植） */
    $dir = rtrim(str_replace('\\', '/', dirname($script)), '/');
    if (substr($dir, -6) === '/pages') {
        $dir = substr($dir, 0, -6);
    }
    if (substr($dir, -5) === '/cron') {
        $dir = substr($dir, 0, -5);
    }
    $base = ($dir === '' || $dir === '.') ? '/' : $dir . '/';
    return $base;
}

/** 站内绝对路径 u('pages/cards.php') */
function u($path = '')
{
    return app_base() . ltrim((string)$path, '/');
}

function redirect($path)
{
    $to = (strncmp($path, 'http://', 7) === 0 || strncmp($path, 'https://', 8) === 0)
        ? $path : u($path);
    if (!headers_sent()) {
        header('Location: ' . $to);
        header('Cache-Control: no-store');
    }
    echo '<!doctype html><meta charset="utf-8"><script>location.replace(' . json_encode($to) . ');</script>';
    echo '<a href="' . e($to) . '">跳转中…</a>';
    exit;
}

/** 重定向回当前脚本（PRG 模式，避免刷新重复提交） */
function redirect_self()
{
    $script = isset($_SERVER['SCRIPT_NAME']) ? str_replace('\\', '/', (string)$_SERVER['SCRIPT_NAME']) : '/index.php';
    $base   = app_base();
    $rel    = strncmp($script, $base, strlen($base)) === 0 ? substr($script, strlen($base)) : ltrim($script, '/');
    if ($rel === '' || $rel === false) {
        $rel = 'index.php';
    }
    redirect($rel);
}

/** 拼当前页面 URL，保留已有 query 并覆盖部分参数 */
function url_with($overrides = array(), $base_path = null)
{
    $script = isset($_SERVER['SCRIPT_NAME']) ? str_replace('\\', '/', (string)$_SERVER['SCRIPT_NAME']) : '/index.php';
    if ($base_path === null) {
        $base_path = basename($script);
        if (basename(dirname($script)) === 'pages') {
            $base_path = 'pages/' . $base_path;
        }
    }
    $qs = $_GET;
    foreach ($overrides as $k => $v) {
        if ($v === null) {
            unset($qs[$k]);
        } else {
            $qs[$k] = $v;
        }
    }
    $pairs = array();
    foreach ($qs as $k => $v) {
        if (is_array($v)) {
            continue;
        }
        $pairs[] = rawurlencode((string)$k) . '=' . rawurlencode((string)$v);
    }
    return u($base_path) . ($pairs ? ('?' . implode('&', $pairs)) : '');
}

/* ------------------------------------------------------------------ 时间 --- */

function now_ts()
{
    return time();
}

/** unix 时间戳 -> 本地时间字符串 */
function fmt_ts($ts, $def = '—')
{
    $ts = (int)$ts;
    if ($ts <= 0) {
        return $def;
    }
    return date('Y-m-d H:i:s', $ts);
}

/** DATETIME 字符串 -> 输出 */
function fmt_dt($dt, $def = '—')
{
    $dt = trim((string)$dt);
    if ($dt === '' || $dt === '0000-00-00 00:00:00') {
        return $def;
    }
    return $dt;
}

/** 到期时间展示 */
function fmt_expire($ts)
{
    $ts = (int)$ts;
    if ($ts <= 0) {
        return '永不过期';
    }
    return date('Y-m-d H:i:s', $ts);
}

/** 是否已过期 */
function is_expired($ts)
{
    $ts = (int)$ts;
    return $ts > 0 && $ts < time();
}

/** 距离 d 天后的时间戳 */
function ts_add_days($base_ts, $days)
{
    $base_ts = (int)$base_ts;
    if ($base_ts <= 0) {
        $base_ts = time();
    }
    return $base_ts + ((int)$days * 86400);
}

/** 人话：还有多久 / 过期多久 */
function human_left($ts)
{
    $ts = (int)$ts;
    if ($ts <= 0) {
        return '永不过期';
    }
    $d = $ts - time();
    $suffix = $d >= 0 ? '后到期' : '前已过期';
    $d = abs($d);
    if ($d < 60) {
        return '不到 1 分钟' . $suffix;
    }
    if ($d < 3600) {
        return floor($d / 60) . ' 分钟' . $suffix;
    }
    if ($d < 86400) {
        return floor($d / 3600) . ' 小时' . $suffix;
    }
    return floor($d / 86400) . ' 天' . $suffix;
}

/** url 用：把 datetime-local 输入转时间戳（空/0 => 0） */
function parse_local_dt($s)
{
    $s = trim((string)$s);
    if ($s === '' || $s === '0') {
        return 0;
    }
    $s = str_replace('T', ' ', $s);
    $ts = strtotime($s);
    return $ts === false ? 0 : (int)$ts;
}

/* ------------------------------------------------------------------ 字符串 -- */

function slen($s)
{
    $s = (string)$s;
    return function_exists('mb_strlen') ? mb_strlen($s, 'UTF-8') : strlen($s);
}

function ssub($s, $start, $len = null)
{
    $s = (string)$s;
    if (function_exists('mb_substr')) {
        return $len === null ? mb_substr($s, $start, null, 'UTF-8') : mb_substr($s, $start, $len, 'UTF-8');
    }
    return $len === null ? substr($s, $start) : substr($s, $start, $len);
}

function has_str($haystack, $needle)
{
    return $needle === '' ? true : (strpos((string)$haystack, (string)$needle) !== false);
}

/* ------------------------------------------------ 卡类型 / 设备上限 --- */

/** 卡类型规范化：只认 free，其余一律按 paid（与 sdkcard 的默认值一致） */
function card_kind_norm($v)
{
    return trim((string)$v) === 'free' ? 'free' : 'paid';
}

function card_kind_label($kind)
{
    return $kind === 'free' ? '公益卡' : '付费卡';
}

/** 设备上限：公益卡强制 0；付费卡 0..9999 */
function card_max_devices_norm($kind, $v)
{
    if ($kind === 'free') {
        return 0;
    }
    $n = (int)$v;
    if ($n < 0) {
        $n = 0;
    }
    if ($n > 9999) {
        $n = 9999;
    }
    return $n;
}

/** 由 max_devices 派生遗留字段 bind_one（1 台才置 1） */
function card_bind_one_from_max($max)
{
    return ((int)$max === 1) ? 1 : 0;
}

/** 一句人话：设备规则 */
function card_devices_text($kind, $max)
{
    if ($kind === 'free') {
        return '不限设备（账号跟随设备）';
    }
    $n = (int)$max;
    return $n > 0 ? ('最多 ' . $n . ' 台设备') : '不限设备';
}

/** MySQL DATETIME -> epoch 秒（0 = 从未使用） */
function dt_to_epoch($dt)
{
    $dt = trim((string)$dt);
    if ($dt === '' || $dt === '0000-00-00 00:00:00') {
        return 0;
    }
    $ts = strtotime($dt);
    return $ts === false ? 0 : (int)$ts;
}

/** cards.json 的 last_used_at（epoch 数字或日期串）-> epoch 秒 */
function card_last_used_to_epoch($v)
{
    if (is_int($v) || is_float($v)) {
        return (int)$v;
    }
    if (is_string($v)) {
        $v = trim($v);
        if ($v === '') {
            return 0;
        }
        if (preg_match('/^\d+(\.\d+)?$/', $v)) {
            return (int)$v;
        }
        return dt_to_epoch($v);
    }
    return 0;
}

/** 卡密脱敏：abcd****wxyz */
function mask_card($key)
{
    $key = (string)$key;
    $n   = slen($key);
    if ($n === 0) {
        return '';
    }
    if ($n <= 4) {
        return ssub($key, 0, 1) . '***';
    }
    if ($n <= 8) {
        return ssub($key, 0, 2) . '****' . ssub($key, $n - 2);
    }
    return ssub($key, 0, 4) . '****' . ssub($key, $n - 4);
}

function str_limit($s, $n, $tail = '…')
{
    $s = (string)$s;
    return slen($s) > $n ? ssub($s, 0, $n) . $tail : $s;
}

function bytes_human($n)
{
    $n = (float)$n;
    $u = array('B', 'KB', 'MB', 'GB', 'TB');
    $i = 0;
    while ($n >= 1024 && $i < 4) {
        $n /= 1024;
        $i++;
    }
    return ($i === 0 ? (string)(int)$n : number_format($n, 1)) . ' ' . $u[$i];
}

/** 随机 token（hex） */
function rand_token($bytes = 32)
{
    try {
        return bin2hex(random_bytes($bytes));
    } catch (Exception $e) {
        return hash('sha256', uniqid((string)mt_rand(), true) . (string)microtime(true));
    }
}

/** 统一换行，处理粘贴进来的 CRLF */
function norm_lines($text)
{
    $text = str_replace(array("\r\n", "\r"), "\n", (string)$text);
    $out  = array();
    foreach (explode("\n", $text) as $line) {
        $line = trim($line);
        if ($line !== '') {
            $out[] = $line;
        }
    }
    return $out;
}

/* ------------------------------------------------------------------ 目录 --- */

function ensure_dir($dir, $mode = 0755)
{
    if (is_dir($dir)) {
        return true;
    }
    return @mkdir($dir, $mode, true);
}

/** 原子写文件：临时文件 + rename（同目录，跨盘 rename 会失败所以必须同目录） */
function atomic_write($path, $data, $mode = 0640)
{
    $dir = dirname($path);
    if (!is_dir($dir) && !ensure_dir($dir)) {
        return '目录不存在且无法创建：' . $dir;
    }
    $tmp = $path . '.tmp.' . getmypid() . '.' . substr(rand_token(4), 0, 6);
    $fp  = @fopen($tmp, 'wb');
    if ($fp === false) {
        return '无法创建临时文件：' . $tmp . '（检查目录写权限）';
    }
    $bytes = strlen($data);
    $ok    = true;
    if ($bytes > 0) {
        $w = @fwrite($fp, $data);
        if ($w === false || $w < $bytes) {
            $ok = false;
        }
    }
    if ($ok && function_exists('fflush')) {
        @fflush($fp);
    }
    @fclose($fp);
    if (!$ok) {
        @unlink($tmp);
        return '写入临时文件失败：' . $tmp;
    }
    @chmod($tmp, $mode);
    if (!@rename($tmp, $path)) {
        /* 有些环境 rename 跨文件系统会失败；退化为 copy+unlink（仍带锁保护） */
        $copied = @copy($tmp, $path);
        @unlink($tmp);
        if (!$copied) {
            return '替换目标文件失败：' . $path;
        }
    }
    return true;
}

/* ---------------------------------------------------------------- settings -- */

function setting_get($key, $default = null)
{
    if (!isset($GLOBALS['__ca_setting_cache'])) {
        $GLOBALS['__ca_setting_cache'] = array();
        try {
            foreach (db_all('SELECT k, v FROM settings') as $row) {
                $GLOBALS['__ca_setting_cache'][(string)$row['k']] = (string)$row['v'];
            }
        } catch (Throwable $e) {
            /* 表还没建好（安装中）或 DB 不可用：返回默认值即可 */
            $GLOBALS['__ca_setting_cache'] = array();
        }
    }
    if (array_key_exists($key, $GLOBALS['__ca_setting_cache'])) {
        return $GLOBALS['__ca_setting_cache'][$key];
    }
    return $default;
}

function setting_int($key, $default = 0)
{
    $v = setting_get($key, null);
    return ($v === null || $v === '') ? (int)$default : (int)$v;
}

function setting_set($key, $value)
{
    $key   = (string)$key;
    $value = is_bool($value) ? ($value ? '1' : '0') : (string)$value;
    db_run(
        'INSERT INTO settings (k, v) VALUES (?, ?) ON DUPLICATE KEY UPDATE v = VALUES(v)',
        array($key, $value)
    );
    if (!isset($GLOBALS['__ca_setting_cache'])) {
        $GLOBALS['__ca_setting_cache'] = array();
    }
    $GLOBALS['__ca_setting_cache'][$key] = $value;
    return true;
}

/** 丢掉本请求的设置缓存（改完设置后如需重读） */
function setting_reload()
{
    $GLOBALS['__ca_setting_cache'] = array();
    return true;
}

/* --------------------------------------------------------------- 分页渲染 --- */

/**
 * @param int   $page     当前页(1 起)
 * @param int   $per      每页条数
 * @param int   $total    总条数
 * @param array $extra    额外 query 参数（会被 url_with 覆盖）
 * @param string $path    目标页面（相对站点根），默认当前页
 */
function pagination($page, $per, $total, $extra = array(), $path = null)
{
    $per   = max(1, (int)$per);
    $total = max(0, (int)$total);
    $pages = (int)ceil($total / $per);
    if ($pages < 1) {
        $pages = 1;
    }
    $page = clamp_int($page, 1, $pages);
    if ($total <= 0) {
        return '';
    }
    $html = '<div class="pager">';
    $html .= '<span class="pager-info">共 <b>' . number_format($total) . '</b> 条 / ' . $pages . ' 页</span>';

    $mk = function ($p) use ($extra, $path) {
        return url_with(array_merge($extra, array('page' => $p)), $path);
    };

    $win = 2;
    if ($page > 1) {
        $html .= '<a class="pg" href="' . e($mk($page - 1)) . '">上一页</a>';
    }
    if ($page - $win > 1) {
        $html .= '<a class="pg" href="' . e($mk(1)) . '">1</a>';
        if ($page - $win > 2) {
            $html .= '<span class="pg-gap">…</span>';
        }
    }
    for ($p = max(1, $page - $win); $p <= min($pages, $page + $win); $p++) {
        $cls = $p === $page ? 'pg pg-on' : 'pg';
        $html .= '<a class="' . $cls . '" href="' . e($mk($p)) . '">' . $p . '</a>';
    }
    if ($page + $win < $pages) {
        if ($page + $win < $pages - 1) {
            $html .= '<span class="pg-gap">…</span>';
        }
        $html .= '<a class="pg" href="' . e($mk($pages)) . '">' . $pages . '</a>';
    }
    if ($page < $pages) {
        $html .= '<a class="pg" href="' . e($mk($page + 1)) . '">下一页</a>';
    }
    $html .= '</div>';
    return $html;
}

/* --------------------------------------------------------------- sdk.log --- */

/**
 * 解析 sdkcard.py 写的 sdk.log（只读，绝不修改文件）
 *
 * 实际日志格式：
 *   10:17:55 /common/config dev=09a4d0ab0ee93616
 *   BODY {}
 *   LOGIN OK 11111111111 dev=09a4d0ab0ee93616
 *   LOGIN REJECT unknown card 999
 *   QUICK OK 11111111111 dev=09a4d0ab0ee93616
 *
 * 只有 HH:MM:SS 没有日期，所以用文件 mtime 的日期做锚点；若某行时间
 * 明显晚于 mtime 的时刻，认为它属于前一天（日志跨天追加）。
 *
 * @param string $path      日志路径
 * @param int    $max_bytes 只读文件末尾这么多字节（大文件保护）
 * @return array('entries'=>array,'skipped'=>int,'recognized'=>int,'lines'=>int,
 *               'err'=>string,'mtime'=>int,'bytes'=>int,'truncated'=>bool)
 */
function parse_sdk_log($path, $max_bytes = 2097152)
{
    $res = array(
        'entries' => array(), 'skipped' => 0, 'recognized' => 0, 'lines' => 0,
        'err' => '', 'mtime' => 0, 'bytes' => 0, 'truncated' => false,
    );
    if (!is_file($path)) {
        $res['err'] = '日志文件不存在：' . $path;
        return $res;
    }
    if (!is_readable($path)) {
        $res['err'] = '日志文件不可读（权限问题）：' . $path;
        return $res;
    }
    $size = (int)@filesize($path);
    $mt   = (int)@filemtime($path);
    $res['bytes'] = $size;
    $res['mtime'] = $mt;

    $start = 0;
    if ($size > $max_bytes) {
        $start = $size - $max_bytes;
        $res['truncated'] = true;
    }
    $fp = @fopen($path, 'rb');
    if ($fp === false) {
        $res['err'] = '打开日志失败：' . $path;
        return $res;
    }
    if ($start > 0) {
        @fseek($fp, $start);
    }
    $raw = @stream_get_contents($fp);
    @fclose($fp);
    if ($raw === false) {
        $res['err'] = '读取日志失败';
        return $res;
    }
    if ($start > 0) {
        $nl = strpos($raw, "\n");
        if ($nl !== false) {
            $raw = substr($raw, $nl + 1);   /* 丢掉被截断的半行 */
        }
    }

    $anchor = $mt > 0 ? $mt : time();
    $y = (int)date('Y', $anchor);
    $m = (int)date('n', $anchor);
    $d = (int)date('j', $anchor);
    $cursor = 0;   /* 最近一条请求行的时间，随后的事件行沿用 */

    foreach (explode("\n", $raw) as $ln) {
        $line = rtrim($ln, "\r");
        if ($line === '') {
            continue;
        }
        $res['lines']++;

        /* 请求行：HH:MM:SS /path dev=<dev> */
        if (preg_match('/^(\d{2}):(\d{2}):(\d{2})\s+(\/\S*)\s+dev=(.*)$/', $line, $mm)) {
            $hh = (int)$mm[1];
            $mi = (int)$mm[2];
            $ss = (int)$mm[3];
            if ($hh < 24 && $mi < 60 && $ss < 61) {
                $t = mktime($hh, $mi, $ss, $m, $d, $y);
                if ($t !== false) {
                    if ($t > $anchor + 120) {
                        $t -= 86400;
                    }
                    $cursor = (int)$t;
                }
            }
            $res['recognized']++;
            continue;
        }

        /* LOGIN OK <card> dev=<dev> */
        if (preg_match('/^LOGIN OK\s+(\S*)\s+dev=(\S*)\s*$/', $line, $mm)) {
            $res['recognized']++;
            $res['entries'][] = array(
                'result' => 'ok', 'card' => $mm[1], 'device' => $mm[2], 'source' => 'sdk.log',
                'ts' => $cursor > 0 ? $cursor : $anchor, 'raw' => $line,
            );
            continue;
        }

        /* QUICK OK <card> dev=<dev> */
        if (preg_match('/^QUICK OK\s+(\S*)\s+dev=(\S*)\s*$/', $line, $mm)) {
            $res['recognized']++;
            $res['entries'][] = array(
                'result' => 'ok', 'card' => $mm[1], 'device' => $mm[2], 'source' => 'sdk.log:quick',
                'ts' => $cursor > 0 ? $cursor : $anchor, 'raw' => $line,
            );
            continue;
        }

        /* LOGIN REJECT unknown card <card>  （sdkcard.py 只写这一种拒绝） */
        if (preg_match('/^LOGIN REJECT\s+(.*?)\s*dev=(\S*)\s*$/', $line, $mm)) {
            $res['recognized']++;
            $card = preg_replace('/^unknown card\s*/i', '', $mm[1]);
            $res['entries'][] = array(
                'result' => 'reject', 'card' => trim((string)$card), 'device' => $mm[2],
                'source' => 'sdk.log', 'ts' => $cursor > 0 ? $cursor : $anchor, 'raw' => $line,
            );
            continue;
        }
        if (preg_match('/^LOGIN REJECT\s+(.*)$/', $line, $mm)) {
            $res['recognized']++;
            $card = preg_replace('/^unknown card\s*/i', '', $mm[1]);
            $res['entries'][] = array(
                'result' => 'reject', 'card' => trim((string)$card), 'device' => '',
                'source' => 'sdk.log', 'ts' => $cursor > 0 ? $cursor : $anchor, 'raw' => $line,
            );
            continue;
        }

        /* BODY {...}：属于上一条请求的请求体，认识但不算事件 */
        if (strncmp($line, 'BODY', 4) === 0) {
            $res['recognized']++;
            continue;
        }
        /* 启动分隔行 */
        if (strpos($line, '=== our sdk') !== false) {
            $res['recognized']++;
            continue;
        }

        /* 其他 -> 格式不符，跳过并计数 */
        $res['skipped']++;
    }

    return $res;
}

/* ------------------------------------------------------------- 批次/搜索 --- */

/**
 * 把建表 SQL 拆成单条语句（能处理引号、-- 与 # 注释）
 * 给 install.php 执行 schema.sql 用。没有存储过程/触发器，所以不需要 DELIMITER。
 * @return array
 */
function sql_split_statements($sql)
{
    $out   = array();
    $buf   = '';
    $len   = strlen($sql);
    $quote = '';
    for ($i = 0; $i < $len; $i++) {
        $c = $sql[$i];
        if ($quote !== '') {
            $buf .= $c;
            if ($c === '\\' && $i + 1 < $len) {
                $buf .= $sql[$i + 1];
                $i++;
                continue;
            }
            if ($c === $quote) {
                $quote = '';
            }
            continue;
        }
        if ($c === "'" || $c === '"' || $c === '`') {
            $quote = $c;
            $buf  .= $c;
            continue;
        }
        /* 行注释：-- 或 #（## 不算） */
        if (($c === '-' && $i + 1 < $len && $sql[$i + 1] === '-')
            || ($c === '#' && ($i + 1 >= $len || $sql[$i + 1] !== '#'))) {
            $nl = strpos($sql, "\n", $i);
            if ($nl === false) {
                break;
            }
            $i = $nl;
            $buf .= "\n";
            continue;
        }
        if ($c === ';') {
            $t = trim($buf);
            if ($t !== '') {
                $out[] = $t;
            }
            $buf = '';
            continue;
        }
        $buf .= $c;
    }
    $t = trim($buf);
    if ($t !== '') {
        $out[] = $t;
    }
    return $out;
}

/** LIKE 通配符转义（配合 ESCAPE '\\' 或默认行为） */
function like_escape($s)
{
    return str_replace(array('\\', '%', '_'), array('\\\\', '\\%', '\\_'), (string)$s);
}

/** 记住最近一次批量生成的 id 列表（用于"一键导出本批"） */
function batch_ids_save($ids)
{
    $ids = array_slice(array_values(array_filter(array_map('intval', (array)$ids))), 0, MAX_BATCH_GEN);
    setting_set('last_batch_ids', json_encode($ids));
    setting_set('last_batch_at', time());
    setting_set('last_batch_count', count($ids));
    return count($ids);
}

function batch_ids_load()
{
    $raw = (string)setting_get('last_batch_ids', '');
    if ($raw === '') {
        return array();
    }
    $j = json_decode($raw, true);
    if (!is_array($j)) {
        return array();
    }
    $out = array();
    foreach ($j as $v) {
        $v = (int)$v;
        if ($v > 0) {
            $out[] = $v;
        }
    }
    return $out;
}

/**
 * 客户端卡密格式：1 开头 + 共 11 位纯数字（正则 ^1\d{10}$）。
 *
 * 这不是运营偏好，是客户端硬限制：国服客户端的卡密输入框 maxLength=11、
 * 数字键盘、正则 ^1\d{10}$ 全部硬编码在 dex 里（实测改 dex 会闪退），
 * 所以只有这个格式的卡密能被用户输进去并提交。
 */
function card_key_is_client_compatible($key)
{
    /* 与客户端 ^1\d{10}$ 等价；用 [0-9] 避免 locale / 未加 u 修饰符时的歧义 */
    return (bool)preg_match('/^1[0-9]{10}$/', (string)$key);
}

/**
 * 生成一张客户端可用的卡密：'1' + 10 位随机数字（共 11 位）。
 *
 * 随机源必须是密码学安全的 random_int()；绝不回退到 rand()/mt_rand()。
 * $len / $charset / $prefix 三个形参只为兼容旧调用点保留，实际一律忽略。
 * 本函数只保证格式、不查库；需要查重请用 gen_card_key_unique()。
 */
function gen_card_key($len = 11, $charset = '', $prefix = '')
{
    $key = '1';
    for ($i = 0; $i < 10; $i++) {
        $key .= (string)random_int(0, 9);
    }
    return $key;
}

/**
 * 生成一张数据库里不存在的卡密（格式见 gen_card_key）。
 *
 * 每生成一张就去 cards.card_key 查一次重（有 uk_cards_card_key 唯一索引），
 * 冲突时最多重试 $max_tries 次；仍然冲突就抛 RuntimeException，
 * 绝不静默返回重复值，由调用方把错误显示给管理员。
 */
function gen_card_key_unique($max_tries = 10)
{
    $max_tries = clamp_int($max_tries, 1, 100);
    for ($i = 0; $i < $max_tries; $i++) {
        $key = gen_card_key();
        $dup = (int)db_val('SELECT COUNT(*) FROM cards WHERE card_key = ?', array($key), 0);
        if ($dup === 0) {
            return $key;
        }
    }
    throw new RuntimeException(
        '卡密生成失败：连续 ' . $max_tries . ' 次生成的卡密都已在数据库里（11 位数字空间可能已接近耗尽），请重试'
    );
}

/* ------------------------------------------------------------------ 布局 --- */

function nav_items()
{
    return array(
        'dashboard' => array('仪表盘', 'pages/dashboard.php'),

        /* 玩家域：全部走 Shittim admin API */
        '__g_player' => array('玩家', null),
        'players'    => array('玩家列表', 'pages/players.php'),
        'bans'       => array('封禁管理', 'pages/bans.php'),
        'mail'       => array('发奖 / 邮件', 'pages/mail.php'),
        'currency'   => array('货币调整', 'pages/currency.php'),
        'items'      => array('道具 / 角色', 'pages/items.php'),
        'console'    => array('GM 命令台', 'pages/console.php'),
        'gacha'      => array('抽卡概率', 'pages/gacha_rates.php'),

        /* 卡密域：现有能力，逻辑不动 */
        '__g_card' => array('卡密', null),
        'cards'    => array('卡密管理', 'pages/cards.php'),
        'new'      => array('新建卡密', 'pages/cards_new.php'),
        'import'   => array('批量导入', 'pages/cards_import.php'),

        /* 系统域 */
        '__g_sys'  => array('系统', null),
        'logs'     => array('登录日志', 'pages/logs.php'),
        'admins'   => array('管理员', 'pages/admins.php'),
        'audit'    => array('审计日志', 'pages/audit.php'),
        'settings' => array('系统设置', 'pages/settings.php'),
    );
}

/**
 * 输出页面头（含侧栏、顶栏、消息条）
 * @param string $title  页面标题
 * @param string $active 当前导航 key
 */
function page_header($title, $active = '')
{
    $admin  = function_exists('current_admin') ? current_admin() : null;
    $flashes = function_exists('flash_take') ? flash_take() : array();
    $css_v  = @filemtime(APP_ROOT . '/assets/app.css');
    $js_v   = @filemtime(APP_ROOT . '/assets/app.js');
    header('Content-Type: text/html; charset=utf-8');
    header('X-Frame-Options: DENY');
    header('X-Content-Type-Options: nosniff');
    header('Referrer-Policy: same-origin');
    header('Cache-Control: no-store, no-cache, must-revalidate');
    ?><!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title><?php echo e($title); ?> · <?php echo e(APP_NAME); ?></title>
<link rel="stylesheet" href="<?php echo e(u('assets/app.css')); ?><?php echo $css_v ? ('?v=' . $css_v) : ''; ?>">
</head>
<body>
<div class="layout">
  <aside class="sidebar" id="ca-sidebar">
    <div class="brand">
      <span class="brand-dot"></span>
      <span class="brand-name"><?php echo e(APP_NAME); ?></span>
    </div>
    <nav class="nav">
      <?php foreach (nav_items() as $key => $item) {
          if ($item[1] === null) { ?>
        <div class="nav-group"><?php echo e($item[0]); ?></div>
      <?php } else { ?>
        <a class="nav-link<?php echo $active === $key ? ' nav-on' : ''; ?>" href="<?php echo e(u($item[1])); ?>"><?php echo e($item[0]); ?></a>
      <?php }
      } ?>
    </nav>
    <div class="side-foot">
      <div class="who"><?php echo $admin ? e($admin['username']) : '—'; ?></div>
      <a class="logout" href="<?php echo e(u('logout.php')); ?>">退出登录</a>
    </div>
  </aside>
  <main class="main">
    <header class="topbar">
      <button type="button" class="burger" id="ca-burger" aria-label="菜单">☰</button>
      <h1 class="page-title"><?php echo e($title); ?></h1>
      <div class="topbar-right">
        <span class="phpver">PHP <?php echo e(PHP_VERSION); ?></span>
      </div>
    </header>
    <div class="content">
<?php
    foreach ($flashes as $f) {
        echo '<div class="alert alert-' . e($f['type']) . '">' . e($f['msg']) . '</div>';
    }
}

function page_footer()
{
    $js_v = @filemtime(APP_ROOT . '/assets/app.js');
    ?>
    </div><!-- /.content -->
    <footer class="foot">
      MySQL ⇄ cards.json 同步由 cron 负责 · 变更最多 1 分钟生效
    </footer>
  </main>
</div>
<script src="<?php echo e(u('assets/app.js')); ?><?php echo $js_v ? ('?v=' . $js_v) : ''; ?>"></script>
</body>
</html><?php
}

/** 一条消息条（不经过 flash，直接渲染） */
function alert_box($msg, $type = 'info')
{
    if ($msg === '' || $msg === null) {
        return '';
    }
    return '<div class="alert alert-' . e($type) . '">' . e($msg) . '</div>';
}
