<?php
/**
 * index.php — 首页（已登录显示仪表盘，未登录跳登录页）
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/inc/auth.php';

if (!db_installed()) {
    redirect('install.php');
}

require_login();

/* 仪表盘以 include 方式渲染，这样 / 与 /pages/dashboard.php 都能用 */
require __DIR__ . '/pages/dashboard.php';
