<?php
/**
 * inc/auth.php — 登录状态、会话表、CSRF、审计日志
 *
 * 设计：不使用 PHP 自带 session 存储（宝塔默认 session 目录常不可写），
 * 而是自定义 Cookie + sessions 表；token 为 32 字节随机 hex。
 * Cookie: HttpOnly + SameSite=Strict（https 时再加 Secure）。
 */

if (!defined('CARDADMIN')) {
    http_response_code(403);
    exit('403 Forbidden');
}

require_once __DIR__ . '/helpers.php';

/* ---------------------------------------------------------------- 公共 --- */

function is_https()
{
    if (!empty($_SERVER['HTTPS']) && strtolower((string)$_SERVER['HTTPS']) !== 'off') {
        return true;
    }
    if (isset($_SERVER['HTTP_X_FORWARDED_PROTO']) && strtolower((string)$_SERVER['HTTP_X_FORWARDED_PROTO']) === 'https') {
        return true;
    }
    if (isset($_SERVER['SERVER_PORT']) && (int)$_SERVER['SERVER_PORT'] === 443) {
        return true;
    }
    return false;
}

function client_ip()
{
    /* 只看 REMOTE_ADDR，避免被 X-Forwarded-For 伪造（面板通常直接对外） */
    $ip = isset($_SERVER['REMOTE_ADDR']) ? (string)$_SERVER['REMOTE_ADDR'] : '';
    return $ip === '' ? '0.0.0.0' : substr($ip, 0, 45);
}

function user_agent()
{
    $ua = isset($_SERVER['HTTP_USER_AGENT']) ? (string)$_SERVER['HTTP_USER_AGENT'] : '';
    return substr($ua, 0, 255);
}

function ca_cookie_set($name, $value, $expires)
{
    $opts = array(
        'expires'  => (int)$expires,
        'path'     => app_base(),
        'httponly' => true,
        'samesite' => 'Strict',
        'secure'   => is_https(),
    );
    if (PHP_VERSION_ID >= 70300) {
        setcookie($name, $value, $opts);
    } else {
        setcookie($name, $value, (int)$expires, app_base() . '; samesite=Strict', '', is_https(), true);
    }
}

function ca_cookie_get($name)
{
    return isset($_COOKIE[$name]) ? (string)$_COOKIE[$name] : '';
}

/* -------------------------------------------------------------- 会话状态 --- */

/** 丢掉本请求的会话缓存（登录/退出/读取 flash 之后必须调用） */
function auth_session_forget()
{
    unset($GLOBALS['__ca_sess']);
}

function auth_session_row()
{
    if (array_key_exists('__ca_sess', $GLOBALS)) {
        return $GLOBALS['__ca_sess'];
    }
    $row = null;
    $GLOBALS['__ca_sess'] = null;
    if (!db_installed()) {
        return $row;
    }
    $token = ca_cookie_get(SESSION_COOKIE);
    if ($token === '' || !preg_match('/^[a-f0-9]{64}$/', $token)) {
        return $row;
    }
    try {
        $r = db_row(
            'SELECT s.token, s.admin_id, s.created_at, s.expires_at, s.ip, s.user_agent, s.csrf, s.flash,
                    a.username, a.enabled, a.pass_hash
               FROM sessions s
               JOIN admins a ON a.id = s.admin_id
              WHERE s.token = ?
              LIMIT 1',
            array($token)
        );
    } catch (Throwable $e) {
        return $row;
    }
    if (!$r) {
        return $row;
    }
    if ((int)$r['expires_at'] <= time()) {
        try {
            db_run('DELETE FROM sessions WHERE token = ?', array($token));
        } catch (Throwable $e) {
            /* ignore */
        }
        return $row;
    }
    if ((int)$r['enabled'] !== 1) {
        return $row;
    }
    $GLOBALS['__ca_sess'] = $r;
    return $r;
}

/** 当前登录管理员（未登录返回 null） */
function current_admin()
{
    $r = auth_session_row();
    if (!$r) {
        return null;
    }
    return array(
        'id'       => (int)$r['admin_id'],
        'username' => (string)$r['username'],
    );
}

function current_session_token()
{
    $r = auth_session_row();
    return $r ? (string)$r['token'] : '';
}

/** 未登录 -> 跳登录页 */
function require_login()
{
    if (!db_installed()) {
        redirect('install.php');
    }
    if (current_admin() === null) {
        $next = isset($_SERVER['REQUEST_URI']) ? (string)$_SERVER['REQUEST_URI'] : '';
        $to   = 'login.php';
        if ($next !== '' && strpos($next, "\n") === false) {
            /* 只允许站内相对路径，防开放重定向 */
            $p = parse_url($next, PHP_URL_PATH);
            if (is_string($p) && $p !== '' && strpos($p, 'login.php') === false
                && strpos($p, 'logout.php') === false && strpos($p, 'install.php') === false) {
                $to .= '?next=' . rawurlencode($p);
            }
        }
        redirect($to);
    }
}

/* ---------------------------------------------------------------- 登录 --- */

/**
 * 登录尝试
 * @return array(ok=>bool, msg=>string)
 */
function auth_attempt_login($username, $password)
{
    if (!db_installed()) {
        return array(false, '尚未安装，请先访问 install.php');
    }
    $ip    = client_ip();
    $now   = time();
    $since = $now - LOGIN_LOCK_SEC;

    /* 清理过期失败记录（低频） */
    if (mt_rand(1, 50) === 1) {
        try {
            db_run('DELETE FROM login_attempts WHERE ts < ?', array($now - 86400));
            db_run('DELETE FROM sessions WHERE expires_at < ?', array($now));
        } catch (Throwable $e) {
            /* ignore */
        }
    }

    $fails = (int)db_val(
        'SELECT COUNT(*) FROM login_attempts WHERE ip = ? AND ok = 0 AND ts > ?',
        array($ip, $since),
        0
    );
    if ($fails >= LOGIN_MAX_FAIL) {
        $last = (int)db_val(
            'SELECT MAX(ts) FROM login_attempts WHERE ip = ? AND ok = 0 AND ts > ?',
            array($ip, $since),
            0
        );
        $left = max(1, (int)ceil(($last + LOGIN_LOCK_SEC - $now) / 60));
        return array(false, '密码错误次数过多，已锁定，请 ' . $left . ' 分钟后再试');
    }

    $username = trim((string)$username);
    $row      = null;
    if ($username !== '') {
        $row = db_row('SELECT * FROM admins WHERE username = ? LIMIT 1', array($username));
    }

    $ok = false;
    if ($row && (int)$row['enabled'] === 1) {
        $stored = (string)$row['pass_hash'];
        $salt   = isset($row['salt']) ? (string)$row['salt'] : '';
        $pw     = $salt !== '' ? hash_hmac('sha256', $password, $salt) : $password;
        if (password_verify($pw, $stored)) {
            $ok = true;
        } elseif (password_verify($password, $stored)) {
            /* 兼容无 salt 直接存密码的旧数据 */
            $ok = true;
        }
    }

    try {
        db_run(
            'INSERT INTO login_attempts (ip, username, ts, ok) VALUES (?, ?, ?, ?)',
            array($ip, $username, $now, $ok ? 1 : 0)
        );
    } catch (Throwable $e) {
        /* ignore */
    }

    if (!$ok) {
        usleep(300000);   /* 失败统一放慢 0.3s */
        if ($row && (int)$row['enabled'] !== 1) {
            return array(false, '该管理员已被禁用');
        }
        return array(false, '用户名或密码错误');
    }

    /* 登录成功：清失败计数、建会话 */
    try {
        db_run('DELETE FROM login_attempts WHERE ip = ? AND ok = 0', array($ip));
    } catch (Throwable $e) {
        /* ignore */
    }

    $token = rand_token(32);
    $csrf  = rand_token(16);
    $exp   = $now + (int)SESSION_TTL;
    db_run(
        'INSERT INTO sessions (token, admin_id, created_at, expires_at, ip, user_agent, csrf, flash)
         VALUES (?, ?, ?, ?, ?, ?, ?, NULL)',
        array($token, (int)$row['id'], $now, $exp, $ip, user_agent(), $csrf)
    );
    db_run(
        'UPDATE admins SET last_login_at = ?, last_login_ip = ? WHERE id = ?',
        array(date('Y-m-d H:i:s', $now), $ip, (int)$row['id'])
    );
    ca_cookie_set(SESSION_COOKIE, $token, $exp);
    $_COOKIE[SESSION_COOKIE] = $token;
    auth_session_forget();          /* 让当前请求立即看到新会话（flash/审计用） */
    preauth_token_clear();          /* 登录前的匿名 CSRF 令牌用完即删 */
    audit_log('login', '管理员 ' . (string)$row['username'], '登录成功，IP=' . $ip);
    return array(true, '登录成功');
}

function auth_logout()
{
    $row = auth_session_row();
    if ($row) {
        try {
            db_run('DELETE FROM sessions WHERE token = ?', array((string)$row['token']));
        } catch (Throwable $e) {
            /* ignore */
        }
        audit_log('logout', '管理员 ' . (string)$row['username'], '退出登录');
    }
    ca_cookie_set(SESSION_COOKIE, '', time() - 3600);
    if (isset($_COOKIE[SESSION_COOKIE])) {
        unset($_COOKIE[SESSION_COOKIE]);
    }
    auth_session_forget();
}

/* ---------------------------------------------------------------- CSRF --- */

function csrf_token()
{
    $row = auth_session_row();
    if ($row && !empty($row['csrf'])) {
        return (string)$row['csrf'];
    }
    /* 登录页（无会话）：令牌存服务端 state/，cookie 只放一个不透明的随机 id。
       这样 token 不再由客户端 cookie 持有（防固定/伪造）。 */
    return preauth_token_get();
}

/* ------------------------------------------------ 登录前（匿名）CSRF 会话 --- */

function preauth_id()
{
    $t = ca_cookie_get('ca_preid');
    if ($t === '' || !preg_match('/^[a-f0-9]{32}$/', $t)) {
        $t = rand_token(16);
        ca_cookie_set('ca_preid', $t, time() + 3600);
        $_COOKIE['ca_preid'] = $t;
    }
    return $t;
}

function preauth_token_file()
{
    $dir = defined('APP_STATE_DIR') ? APP_STATE_DIR : sys_get_temp_dir();
    return $dir . '/precsrf_' . substr(hash('sha256', preauth_id()), 0, 24) . '.json';
}

function preauth_token_get()
{
    $dir = defined('APP_STATE_DIR') ? APP_STATE_DIR : sys_get_temp_dir();
    if (!is_dir($dir) && function_exists('ensure_dir')) {
        @ensure_dir($dir);
    }
    $f   = preauth_token_file();
    $now = time();
    $raw = @file_get_contents($f);
    if ($raw !== false) {
        $j = json_decode($raw, true);
        if (is_array($j) && isset($j['t'], $j['exp']) && (int)$j['exp'] > $now
            && preg_match('/^[a-f0-9]{32}$/', (string)$j['t'])) {
            return (string)$j['t'];
        }
    }
    $t = rand_token(16);
    @file_put_contents($f, json_encode(array('t' => $t, 'exp' => $now + 3600)), LOCK_EX);
    @chmod($f, 0600);
    return $t;
}

function preauth_token_clear()
{
    $f = preauth_token_file();
    if (is_file($f)) {
        @unlink($f);
    }
}

/* --------------------------------------------------- 一次性展示的秘密值 --- */
/* 用于「点一次显示」这类场景：值存服务端 state/，下次请求取走即删（TTL 120s）。 */
function secret_once_file($key)
{
    $sid = current_session_token();
    if ($sid === '') {
        return '';
    }
    $dir = defined('APP_STATE_DIR') ? APP_STATE_DIR : sys_get_temp_dir();
    return $dir . '/secret_' . substr(hash('sha256', $sid . '|' . (string)$key), 0, 24) . '.json';
}

function secret_once_set($key, $value, $ttl = 120)
{
    $f = secret_once_file($key);
    if ($f === '') {
        return false;
    }
    $dir = dirname($f);
    if (!is_dir($dir) && function_exists('ensure_dir')) {
        @ensure_dir($dir);
    }
    if (mt_rand(1, 50) === 1) {
        foreach ((array)@glob($dir . '/secret_*.json') as $old) {
            if (@filemtime($old) < time() - 3600) {
                @unlink($old);
            }
        }
    }
    @file_put_contents($f, json_encode(array('v' => (string)$value, 'exp' => time() + (int)$ttl)), LOCK_EX);
    @chmod($f, 0600);
    return true;
}

function secret_once_take($key)
{
    $f = secret_once_file($key);
    if ($f === '' || !is_file($f)) {
        return '';
    }
    $raw = @file_get_contents($f);
    @unlink($f);
    $j = $raw === false ? null : json_decode($raw, true);
    if (!is_array($j) || !isset($j['v'], $j['exp']) || (int)$j['exp'] < time()) {
        return '';
    }
    return (string)$j['v'];
}

function csrf_field()
{
    return '<input type="hidden" name="_csrf" value="' . e(csrf_token()) . '">';
}

/** 校验 POST 的 CSRF，失败直接 419 结束 */
function verify_csrf()
{
    $sent = isset($_POST['_csrf']) ? (string)$_POST['_csrf'] : '';
    $want = csrf_token();
    if ($sent === '' || $want === '' || !hash_equals($want, $sent)) {
        http_response_code(419);
        header('Content-Type: text/html; charset=utf-8');
        echo '<!doctype html><meta charset="utf-8"><div style="font:16px/1.6 sans-serif;padding:40px">';
        echo '<h3>安全校验失败（CSRF token 无效）</h3>';
        echo '<p>请返回上一页刷新后重试。会话可能已过期。</p>';
        echo '<p><a href="' . e(u('index.php')) . '">返回首页</a></p></div>';
        exit;
    }
    return true;
}

/** 要求必须是 POST + 通过 CSRF */
function require_post_csrf()
{
    if (!isset($_SERVER['REQUEST_METHOD']) || strtoupper((string)$_SERVER['REQUEST_METHOD']) !== 'POST') {
        http_response_code(405);
        header('Allow: POST');
        exit('405 Method Not Allowed');
    }
    verify_csrf();
    return true;
}

/* ------------------------------------------- 高危操作的一次性确认令牌 --- */

/**
 * 防误触（不是防攻击）：高危动作必须带服务端生成的一次性令牌。
 * 令牌存 state/otok_<hash>.json，POST 校验后立即删除；TTL 10 分钟。
 * 每个 (会话, scope) 同时只有一个有效令牌——多标签页只保留最新那个。
 */
function action_token_file($scope)
{
    $sid = current_session_token();
    if ($sid === '') {
        return '';
    }
    $dir = defined('APP_STATE_DIR') ? APP_STATE_DIR : sys_get_temp_dir();
    return $dir . '/otok_' . substr(hash('sha256', $sid . '|' . (string)$scope), 0, 24) . '.json';
}

function action_token_get($scope, $ttl = 600)
{
    $f = action_token_file($scope);
    if ($f === '') {
        return '';
    }
    $dir = dirname($f);
    if (!is_dir($dir) && function_exists('ensure_dir')) {
        @ensure_dir($dir);
    }
    $now = time();
    if (mt_rand(1, 50) === 1) {
        foreach ((array)@glob($dir . '/otok_*.json') as $old) {
            if (@filemtime($old) < $now - 7200) {
                @unlink($old);
            }
        }
    }
    $raw = @file_get_contents($f);
    if ($raw !== false) {
        $j = json_decode($raw, true);
        if (is_array($j) && isset($j['t'], $j['exp']) && (int)$j['exp'] > $now
            && preg_match('/^[a-f0-9]{32}$/', (string)$j['t'])) {
            return (string)$j['t'];
        }
    }
    $t = rand_token(16);
    @file_put_contents($f, json_encode(array('t' => $t, 'exp' => $now + (int)$ttl)), LOCK_EX);
    @chmod($f, 0600);
    return $t;
}

function action_token_field($scope)
{
    $t = action_token_get($scope);
    if ($t === '') {
        return '';
    }
    return '<input type="hidden" name="_atoken" value="' . e($t) . '">';
}

function action_token_check($scope)
{
    $sent = isset($_POST['_atoken']) ? (string)$_POST['_atoken'] : '';
    $f    = action_token_file($scope);
    $ok   = false;
    if ($f !== '' && $sent !== '' && is_file($f)) {
        $raw = @file_get_contents($f);
        $j   = $raw === false ? null : json_decode($raw, true);
        if (is_array($j) && isset($j['t'], $j['exp']) && (int)$j['exp'] >= time()
            && hash_equals((string)$j['t'], $sent)) {
            $ok = true;
        }
        @unlink($f);          /* 一次性：无论校验成败都作废 */
    }
    if (!$ok) {
        http_response_code(419);
        header('Content-Type: text/html; charset=utf-8');
        echo '<!doctype html><meta charset="utf-8"><div style="font:16px/1.6 sans-serif;padding:40px">';
        echo '<h3>操作确认已失效（一次性令牌）</h3>';
        echo '<p>高危操作需要在页面上重新确认。可能原因：令牌过期、重复提交、或页面已刷新。</p>';
        echo '<p><a href="' . e(u('index.php')) . '">返回首页</a></p></div>';
        exit;
    }
    return true;
}

/* -------------------------------------------------------------- flash --- */

/** 一次性提示消息（存在 sessions.flash 里，不需要额外的 PHP session） */
function flash_set($msg, $type = 'ok')
{
    $row = auth_session_row();
    $msg = (string)$msg;
    if (!$row) {
        return false;
    }
    $payload = json_encode(array(array('msg' => $msg, 'type' => $type)), JSON_UNESCAPED_UNICODE);
    try {
        db_run('UPDATE sessions SET flash = ? WHERE token = ?', array($payload, (string)$row['token']));
    } catch (Throwable $e) {
        return false;
    }
    return true;
}

function flash_take()
{
    $row = auth_session_row();
    if (!$row) {
        return array();
    }
    $raw = isset($row['flash']) ? (string)$row['flash'] : '';
    if ($raw === '') {
        return array();
    }
    try {
        db_run('UPDATE sessions SET flash = NULL WHERE token = ?', array((string)$row['token']));
    } catch (Throwable $e) {
        /* ignore */
    }
    $GLOBALS['__ca_sess']['flash'] = null;
    $arr = json_decode($raw, true);
    if (!is_array($arr)) {
        return array();
    }
    $out = array();
    foreach ($arr as $it) {
        if (is_array($it) && isset($it['msg'])) {
            $type = isset($it['type']) ? (string)$it['type'] : 'ok';
            if (!in_array($type, array('ok', 'warn', 'err', 'info'), true)) {
                $type = 'ok';
            }
            $out[] = array('msg' => (string)$it['msg'], 'type' => $type);
        }
    }
    return $out;
}

/* --------------------------------------------------------------- 审计 --- */

/**
 * 所有写操作记一条审计日志
 * @param string $action 动作标识，如 card.create / card.delete
 * @param string $target 影响对象，如 "卡密 1234****abcd"
 * @param string $detail 细节，如 "共 3 条"
 */
function audit_log($action, $target = '', $detail = '')
{
    $row  = auth_session_row();
    $data = array(
        'admin_id'   => $row ? (int)$row['admin_id'] : null,
        'admin_name' => $row ? (string)$row['username'] : 'system',
        'action'     => substr((string)$action, 0, 64),
        'target'     => substr((string)$target, 0, 255),
        'detail'     => substr((string)$detail, 0, 4000),
        'ip'         => client_ip(),
        'ts'         => time(),
    );
    try {
        db_run(
            'INSERT INTO audit_logs (admin_id, admin_name, action, target, detail, ip, ts)
             VALUES (?, ?, ?, ?, ?, ?, ?)',
            array($data['admin_id'], $data['admin_name'], $data['action'], $data['target'],
                  $data['detail'], $data['ip'], $data['ts'])
        );
    } catch (Throwable $e) {
        /* 审计失败不应影响主流程 */
    }
    return true;
}

/* --------------------------------------------------------- 密码相关工具 --- */

function new_salt()
{
    return rand_token(16);
}

/** 生成 pass_hash：bcrypt(hmac_sha256(password, salt))，避免 bcrypt 72 字节截断 */
function make_pass_hash($password, $salt)
{
    return password_hash(hash_hmac('sha256', (string)$password, (string)$salt), PASSWORD_BCRYPT);
}

function check_pass($password, $hash, $salt)
{
    $hash = (string)$hash;
    $salt = (string)$salt;
    if ($salt !== '') {
        return password_verify(hash_hmac('sha256', (string)$password, $salt), $hash);
    }
    return password_verify((string)$password, $hash);
}
