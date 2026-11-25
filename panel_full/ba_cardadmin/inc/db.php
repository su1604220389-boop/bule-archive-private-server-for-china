<?php
/**
 * inc/db.php — PDO 连接 + 常量 + 查询小工具
 *
 * 被 inc/helpers.php 引入，页面不要直接 require 这里。
 * 没有 config.php 时不会 fatal，只是 db_installed() === false，
 * 这样 install.php 与登录页都能正常提示。
 */

if (!defined('CARDADMIN')) {
    http_response_code(403);
    exit('403 Forbidden');
}

/* ---------------------------------------------------------------- 配置 ----- */
$__ca_cfg = dirname(__DIR__) . '/config.php';
if (is_file($__ca_cfg)) {
    require_once $__ca_cfg;
}
unset($__ca_cfg);

if (!defined('DB_NAME') || !defined('DB_HOST') || (string)DB_NAME === '') {
    define('CARDADMIN_INSTALLED', false);
} else {
    define('CARDADMIN_INSTALLED', true);
}

/* 缺省值：config.php 未定义时用这些 */
if (!defined('DB_PORT')) {
    define('DB_PORT', 3306);
}
if (!defined('DB_USER')) {
    define('DB_USER', '');
}
if (!defined('DB_PASS')) {
    define('DB_PASS', '');
}
if (!defined('APP_NAME')) {
    define('APP_NAME', '卡密管理后台');
}
if (!defined('APP_TIMEZONE')) {
    define('APP_TIMEZONE', 'Asia/Shanghai');
}
if (!defined('APP_SECRET')) {
    define('APP_SECRET', '');
}
if (!defined('APP_DEBUG')) {
    define('APP_DEBUG', false);
}
if (!defined('APP_BASE')) {
    define('APP_BASE', '');           /* 留空 = 自动识别（子目录也能跑） */
}
if (!defined('CARDS_JSON_PATH')) {
    define('CARDS_JSON_PATH', '/root/bapatch/cards.json');
}
if (!defined('SDK_LOG_PATH')) {
    define('SDK_LOG_PATH', '/root/bapatch/sdk.log');
}
if (!defined('SESSION_COOKIE')) {
    define('SESSION_COOKIE', 'ca_sid');
}
if (!defined('SESSION_TTL')) {
    define('SESSION_TTL', 43200);     /* 12 小时 */
}
if (!defined('MAX_UPLOAD_BYTES')) {
    define('MAX_UPLOAD_BYTES', 2097152);   /* 2 MB */
}
if (!defined('MAX_BATCH_GEN')) {
    define('MAX_BATCH_GEN', 5000);
}
if (!defined('LOGIN_MAX_FAIL')) {
    define('LOGIN_MAX_FAIL', 5);
}
if (!defined('LOGIN_LOCK_SEC')) {
    define('LOGIN_LOCK_SEC', 600);    /* 10 分钟 */
}
if (!defined('APP_ROOT')) {
    define('APP_ROOT', dirname(__DIR__));
}
if (!defined('APP_STATE_DIR')) {
    define('APP_STATE_DIR', APP_ROOT . '/state');
}
if (!defined('APP_LOG_DIR')) {
    define('APP_LOG_DIR', APP_ROOT . '/logs');
}

@date_default_timezone_set(APP_TIMEZONE);
if (function_exists('mb_internal_encoding')) {
    @mb_internal_encoding('UTF-8');
}

/* ------------------------------------------------------------------ 连接 --- */

function db_installed()
{
    return (bool)CARDADMIN_INSTALLED;
}

/**
 * @return PDO
 * @throws RuntimeException
 */
function db()
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }
    if (!db_installed()) {
        throw new RuntimeException('尚未安装：请先访问 install.php 完成安装');
    }
    $dsn = 'mysql:host=' . DB_HOST . ';port=' . (int)DB_PORT . ';dbname=' . DB_NAME . ';charset=utf8mb4';
    try {
        $pdo = new PDO($dsn, DB_USER, DB_PASS, array(
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
            PDO::ATTR_STRINGIFY_FETCHES  => false,
        ));
    } catch (PDOException $e) {
        /* 不要回显凭据；PDO 的 message 里只有 DSN(host/db) */
        throw new RuntimeException('数据库连接失败：' . $e->getMessage());
    }
    return $pdo;
}

function db_is_ok()
{
    try {
        db()->query('SELECT 1');
        return true;
    } catch (Throwable $e) {
        return false;
    }
}

/**
 * 统一预处理执行（全部 prepared statement，防注入）
 * @param string $sql
 * @param array  $params
 * @return PDOStatement
 */
function db_run($sql, $params = array())
{
    $st = db()->prepare($sql);
    $st->execute($params);
    return $st;
}

function db_all($sql, $params = array())
{
    return db_run($sql, $params)->fetchAll();
}

function db_row($sql, $params = array())
{
    $r = db_run($sql, $params)->fetch();
    return $r === false ? null : $r;
}

function db_val($sql, $params = array(), $default = null)
{
    $v = db_run($sql, $params)->fetchColumn();
    return ($v === false || $v === null) ? $default : $v;
}

function db_insert_id()
{
    return (int)db()->lastInsertId();
}
