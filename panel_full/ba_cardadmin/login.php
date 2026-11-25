<?php
/**
 * login.php — 管理员登录
 * 失败 5 次锁 10 分钟（按 IP，记录在 login_attempts 表）
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/inc/auth.php';

if (!db_installed()) {
    redirect('install.php');
}
if (current_admin() !== null) {
    redirect('index.php');
}

$err = '';
$msg = '';
$username = '';
$next = get_q('next', '');

/* 先落 CSRF cookie（必须在任何输出之前，否则 header 已发出的环境setcookie 会失败） */
csrf_token();
/* 只接受站内相对路径，防开放重定向 */
if ($next !== '' && (strpos($next, '//') !== false || strpos($next, ':') !== false || strpos($next, '\\') !== false)) {
    $next = '';
}

if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    verify_csrf();
    $username = post_q('username');
    $password = post_q('password');
    $next     = post_q('next', '');

    if ($username === '' || $password === '') {
        $err = '请输入用户名和密码';
    } else {
        try {
            $r = auth_attempt_login($username, $password);
            if ($r[0]) {
                $target = 'index.php';
                if ($next !== '' && strpos($next, '//') === false && strpos($next, ':') === false
                    && strpos($next, '\\') === false) {
                    $target = ltrim($next, '/');
                }
                redirect($target);
            }
            $err = $r[1];
        } catch (Throwable $e) {
            /* 数据库挂了也要给出人话，不要白屏 */
            $err = '数据库暂时不可用，请检查 config.php 与 MySQL 状态：' . $e->getMessage();
        }
    }
}

if (get_q('out') === '1') {
    $msg = '已安全退出登录';
}

/* 剩余尝试次数提示 */
$fails_left = null;
if (db_installed()) {
    try {
        $f = (int)db_val(
            'SELECT COUNT(*) FROM login_attempts WHERE ip = ? AND ok = 0 AND ts > ?',
            array(client_ip(), time() - LOGIN_LOCK_SEC),
            0
        );
        $fails_left = max(0, LOGIN_MAX_FAIL - $f);
    } catch (Throwable $e) {
        $fails_left = null;
    }
}

$css_v = @filemtime(APP_ROOT . '/assets/app.css');
header('Content-Type: text/html; charset=utf-8');
header('X-Frame-Options: DENY');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');
?><!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>登录 · <?php echo e(APP_NAME); ?></title>
<link rel="stylesheet" href="<?php echo e(u('assets/app.css')); ?><?php echo $css_v ? ('?v=' . $css_v) : ''; ?>">
</head>
<body class="login-body">
<div class="login-wrap">
  <div class="login-card">
    <div class="login-brand">
      <span class="brand-dot"></span>
      <span><?php echo e(APP_NAME); ?></span>
    </div>
    <p class="login-sub">请输入管理员账号密码</p>

    <?php if ($err !== '') { ?>
      <div class="alert alert-err"><?php echo e($err); ?></div>
    <?php } ?>
    <?php if ($msg !== '') { ?>
      <div class="alert alert-info"><?php echo e($msg); ?></div>
    <?php } ?>

    <form method="post" action="<?php echo e(u('login.php')); ?>" autocomplete="off">
      <?php echo csrf_field(); ?>
      <input type="hidden" name="next" value="<?php echo e($next); ?>">
      <label class="fld">
        <span>用户名</span>
        <input type="text" name="username" value="<?php echo e($username); ?>" maxlength="32"
               autocomplete="username" autocapitalize="off" spellcheck="false" required autofocus>
      </label>
      <label class="fld">
        <span>密码</span>
        <input type="password" name="password" value="" maxlength="200"
               autocomplete="current-password" required>
      </label>
      <button type="submit" class="btn btn-primary btn-block">登录</button>
    </form>

    <?php if ($fails_left !== null) { ?>
      <p class="login-hint">连续失败 5 次将锁定 10 分钟；当前还可尝试 <b><?php echo (int)$fails_left; ?></b> 次</p>
    <?php } ?>
    <p class="login-foot">IP: <?php echo e(client_ip()); ?> · <?php echo e(date('Y-m-d H:i:s')); ?></p>
  </div>
</div>
</body>
</html>
