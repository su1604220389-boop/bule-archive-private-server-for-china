<?php
/**
 * config.php — 由 install.php 于 2026-11-16 05:11:07 自动生成
 *
 * ！！！本文件包含数据库密码，不要提交到 git，不要发给任何人。
 * ！！！如需迁移服务器，请重新跑 install.php，不要直接复制本文件到不可信环境。
 */

if (!defined('CARDADMIN')) { http_response_code(403); exit('403 Forbidden'); }

define('DB_HOST', '127.0.0.1');
define('DB_PORT', 3306);
define('DB_NAME', 'ba_cardadmin');
define('DB_USER', '<REDACTED_DB_CREDENTIAL>');
define('DB_PASS', '<REDACTED_DB_CREDENTIAL>');

define('APP_NAME', '卡密管理后台');
define('APP_SECRET', '<REDACTED_SECRET>');
define('APP_TIMEZONE', 'Asia/Shanghai');
define('APP_DEBUG', false);
define('APP_BASE', '');   // 留空 = 自动识别（子目录部署也能用）

/* 与 sdkcard.py 对接 */
define('CARDS_JSON_PATH', '/www/wwwroot/ba_sdk/cards.json');
define('SDK_LOG_PATH', '/www/wwwroot/ba_sdk/sdk.log');

/* 会话与限制 */
define('SESSION_TTL', 43200);      // 12 小时
define('MAX_UPLOAD_BYTES', 2097152); // 2 MB
define('MAX_BATCH_GEN', 5000);

