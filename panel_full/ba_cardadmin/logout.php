<?php
/**
 * logout.php — 退出登录（删除 sessions 行 + 清 Cookie）
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/inc/auth.php';

auth_logout();
redirect('login.php?out=1');
