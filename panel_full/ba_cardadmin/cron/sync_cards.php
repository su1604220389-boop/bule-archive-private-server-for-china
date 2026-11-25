<?php
/**
 * cron/sync_cards.php — 定时任务：MySQL（唯一真源） -> /root/bapatch/cards.json
 *
 * 只能命令行运行（web 直接访问会立刻 403 退出，不做任何事）。
 * 注意：这里**故意不写 shebang**（#!/usr/bin/env php），
 * 因为 shebang 在 web SAPI 下会被当作输出，导致 header() 失效、状态码错成 200。
 *
 * 用法：
 *   php /path/to/cron/sync_cards.php              # 正常同步
 *   php .../sync_cards.php --dry-run              # 只看会导出多少，不写文件
 *   php .../sync_cards.php --force                # 首次同步时也允许丢弃 json 孤儿卡密
 *   php .../sync_cards.php --import-orphans       # 先把 cards.json 里库里没有的卡密导入库
 *   php .../sync_cards.php --quiet                # 少输出
 *
 * crontab（root）：
 *   * * * * * /usr/bin/php /www/wwwroot/ba_cardadmin/cron/sync_cards.php >> /www/wwwroot/ba_cardadmin/logs/sync.log 2>&1
 */

if (PHP_SAPI !== 'cli') {
    if (!headers_sent()) {
        http_response_code(403);
        header('Content-Type: text/plain; charset=utf-8');
    }
    echo "403 Forbidden: this script is CLI-only\n";
    exit(1);
}

if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once dirname(__DIR__) . '/inc/auth.php';
require_once dirname(__DIR__) . '/inc/sync.php';

/* 日志目录 + 简单轮转（超过 5 MB 只保留后 200 KB） */
@ensure_dir(APP_LOG_DIR);
$slog = sync_log_path();
if (is_file($slog) && (int)@filesize($slog) > 5 * 1024 * 1024) {
    $raw = (string)@file_get_contents($slog, false, null, -200000);
    @file_put_contents($slog, "[rotated " . date('Y-m-d H:i:s') . "]\n" . $raw);
}
@chmod($slog, 0666);

/* 参数 */
$args = array_slice(isset($argv) ? $argv : array(), 1);
$opt  = array('dry_run' => false, 'force' => false, 'quiet' => false, 'import_orphans' => false);
foreach ($args as $a) {
    if ($a === '--dry-run' || $a === '-n') {
        $opt['dry_run'] = true;
    } elseif ($a === '--force' || $a === '-f') {
        $opt['force'] = true;
    } elseif ($a === '--quiet' || $a === '-q') {
        $opt['quiet'] = true;
    } elseif ($a === '--import-orphans') {
        $opt['import_orphans'] = true;
    } elseif ($a === '--help' || $a === '-h') {
        echo basename(__FILE__) . " [--dry-run] [--force] [--import-orphans] [--quiet]\n";
        exit(0);
    } else {
        fwrite(STDERR, "未知参数：{$a}（--help 看用法）\n");
        exit(2);
    }
}

$say = function ($msg) use ($opt) {
    if (!$opt['quiet']) {
        echo '[' . date('Y-m-d H:i:s') . '] ' . $msg . "\n";
    }
};

/* 没装好就别跑，避免把 cards.json 改成空库 */
if (!db_installed()) {
    fwrite(STDERR, "[FATAL] 未安装（缺少 config.php 或 DB_NAME）：先访问 install.php\n");
    exit(1);
}
if (!db_is_ok()) {
    fwrite(STDERR, "[FATAL] 数据库连不上，本次不同步（保持 cards.json 原样）\n");
    sync_log_line('DB 不可用，跳过同步');
    exit(1);
}

/* 面板请求过同步？ */
$flag_info = sync_flag_info();
if ($flag_info !== null) {
    @chmod(sync_flag_path(), 0644);
    $say('发现面板的手动同步请求：' . json_encode($flag_info, JSON_UNESCAPED_UNICODE));
}

$say('开始同步 cards_json=' . sync_json_path());

/* 可选：先导入孤儿 */
if ($opt['import_orphans']) {
    $imp = sync_import_orphans(false);
    $say('导入 cards.json 孤儿：' . $imp['msg'] . ' 新增 ' . $imp['added'] . ' 个，设备 ' . $imp['devices']
        . '，跳过 ' . $imp['skipped']);
    if (!$imp['ok']) {
        fwrite(STDERR, '[ERROR] 导入失败：' . $imp['msg'] . "\n");
        exit(1);
    }
}

$r = sync_cards(array(
    'dry_run' => $opt['dry_run'],
    'force'   => $opt['force'],
    'source'  => $opt['dry_run'] ? 'cron-dry' : 'cron',
));

if (!$r['ok']) {
    fwrite(STDERR, '[FAIL] ' . $r['msg'] . "\n");
    sync_log_line('cron 同步失败：' . $r['msg']);
    exit(1);
}

if ($opt['dry_run']) {
    $say('dry-run：将导出 ' . (int)$r['count'] . ' 个卡密，' . bytes_human((int)$r['bytes'])
        . '，合并设备 ' . (int)$r['imported'] . '，丢弃孤儿 ' . count($r['orphans']));
    exit(0);
}

$say('同步成功：' . (int)$r['count'] . ' 个卡密，' . bytes_human((int)$r['bytes'])
    . '，合并设备 ' . (int)$r['imported']
    . '，丢弃孤儿 ' . count($r['orphans'])
    . '，禁用跳过 ' . (int)$r['disabled']);

if ($flag_info !== null) {
    sync_flag_clear();
    audit_log('sync.cron', 'cards.json', '按面板请求同步：' . (int)$r['count'] . ' 个卡密');
}

/* 让 www 也能读写这个日志（cron 是 root 建的） */
@chmod($slog, 0666);

exit(0);
