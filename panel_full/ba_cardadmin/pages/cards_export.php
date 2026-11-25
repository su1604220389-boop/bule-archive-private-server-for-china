<?php
/**
 * pages/cards_export.php — 导出卡密（txt / csv）
 *
 * GET 参数与列表页一致：q/status/exp/bind/sort/batch，或 batch=last 导出最近一批
 * 导出会暴露明文卡密，所以记一条审计日志。
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';

require_login();

/* F4：导出会暴露明文卡密，改成 POST + CSRF（GET 可被跨站触发/预取/进浏览器历史） */
if (!isset($_SERVER['REQUEST_METHOD']) || strtoupper((string)$_SERVER['REQUEST_METHOD']) !== 'POST') {
    http_response_code(405);
    header('Allow: POST');
    exit('405 Method Not Allowed');
}
verify_csrf();

$format = post_q('format', 'txt');
if ($format !== 'csv' && $format !== 'txt') {
    $format = 'txt';
}

/* ------------------------------------------------------------- 条件拼装 --- */
$where  = array('1=1');
$params = array();
$now    = time();

$q = trim(post_q('q'));
if (slen($q) > 64) {
    $q = ssub($q, 0, 64);
}
if ($q !== '') {
    $where[]  = 'card_key LIKE ?';
    $params[] = '%' . like_escape($q) . '%';
}
$status = post_q('status', 'all');
if (in_array($status, array('active', 'disabled'), true)) {
    $where[]  = 'status = ?';
    $params[] = $status;
}
$exp = post_q('exp', 'all');
if ($exp === 'expired') {
    $where[]  = 'expire_at > 0 AND expire_at < ?';
    $params[] = $now;
} elseif ($exp === 'soon') {
    $where[]  = 'expire_at > 0 AND expire_at >= ? AND expire_at <= ?';
    $params[] = $now;
    $params[] = $now + 7 * 86400;
} elseif ($exp === 'never') {
    $where[] = 'expire_at = 0';
}
$bind = post_q('bind', 'all');
if ($bind === 'bound') {
    $where[] = 'EXISTS (SELECT 1 FROM card_devices d WHERE d.card_id = cards.id)';
} elseif ($bind === 'unbound') {
    $where[] = 'NOT EXISTS (SELECT 1 FROM card_devices d WHERE d.card_id = cards.id)';
}
if (post_q('batch') === 'last') {
    $ids = batch_ids_load();
    if ($ids) {
        $where[] = 'id IN (' . implode(',', array_fill(0, count($ids), '?')) . ')';
        foreach ($ids as $bid) {
            $params[] = (int)$bid;
        }
    } else {
        $where[] = '1 = 0';
    }
}
$wsql = implode(' AND ', $where);

$total = 0;
try {
    $total = (int)db_val('SELECT COUNT(*) FROM cards WHERE ' . $wsql, $params, 0);
} catch (Throwable $e) {
    http_response_code(500);
    header('Content-Type: text/plain; charset=utf-8');
    exit('导出失败：' . $e->getMessage());
}

$stamp = date('Ymd_Hi');
$fname = 'cards_' . $stamp . '.' . $format;

audit_log('card.export', '导出 ' . $format . '（' . $total . ' 条）',
    'q=' . $q . ' status=' . $status . ' exp=' . $exp . ' bind=' . $bind);

/* 清掉可能已经有的输出缓冲，保证文件干净 */
while (ob_get_level() > 0) {
    @ob_end_clean();
}

header('Content-Type: ' . ($format === 'csv' ? 'text/csv; charset=utf-8' : 'text/plain; charset=utf-8'));
header('Content-Disposition: attachment; filename="' . $fname . '"');
header('Content-Transfer-Encoding: binary');
header('Cache-Control: no-store, no-cache, must-revalidate');
header('Pragma: no-cache');
header('Expires: 0');

if ($total === 0) {
    echo $format === 'csv' ? "卡密,状态,到期时间,绑定设备数,设备列表,创建时间,创建人,备注,最后登录,登录次数\n" : '';
    exit;
}

/* ------------------------------------------------------------- 输出 --- */
if ($format === 'txt') {
    $offset = 0;
    $chunk  = 2000;
    while ($offset < $total) {
        $rows = db_all(
            'SELECT card_key FROM cards WHERE ' . $wsql . ' ORDER BY id ASC LIMIT ' . (int)$chunk . ' OFFSET ' . (int)$offset,
            $params
        );
        if (!$rows) {
            break;
        }
        foreach ($rows as $r) {
            echo (string)$r['card_key'] . "\n";
        }
        $offset += count($rows);
    }
    exit;
}

/* CSV：带 BOM，Excel 打开不乱码 */
echo "\xEF\xBB\xBF";
echo "卡密,状态,到期时间,绑定设备数,设备列表,创建时间,创建人,备注,最后登录,登录次数\n";

$offset = 0;
$chunk  = 1000;
while ($offset < $total) {
    $rows = db_all(
        'SELECT id, card_key, status, expire_at, bind_one, created_at, created_by, note,
                login_count, last_login_at
           FROM cards WHERE ' . $wsql . ' ORDER BY id ASC LIMIT ' . (int)$chunk . ' OFFSET ' . (int)$offset,
        $params
    );
    if (!$rows) {
        break;
    }
    /* 设备一次查完 */
    $ids = array();
    foreach ($rows as $r) {
        $ids[] = (int)$r['id'];
    }
    $devmap = array();
    if ($ids) {
        $drows = db_all(
            'SELECT card_id, device_id FROM card_devices WHERE card_id IN ('
            . implode(',', array_fill(0, count($ids), '?')) . ') ORDER BY id ASC',
            $ids
        );
        foreach ($drows as $d) {
            $cid = (int)$d['card_id'];
            if (!isset($devmap[$cid])) {
                $devmap[$cid] = array();
            }
            $devmap[$cid][] = (string)$d['device_id'];
        }
    }

    foreach ($rows as $r) {
        $cid  = (int)$r['id'];
        $devs = isset($devmap[$cid]) ? $devmap[$cid] : array();
        $exp  = (int)$r['expire_at'];
        $line = array(
            (string)$r['card_key'],
            $r['status'] === 'active' ? '启用' : '禁用',
            $exp === 0 ? '永不过期' : date('Y-m-d H:i:s', $exp),
            (string)count($devs),
            implode(' | ', $devs),
            (string)$r['created_at'],
            (string)$r['created_by'],
            (string)$r['note'],
            $r['last_login_at'] === null ? '' : (string)$r['last_login_at'],
            (string)(int)$r['login_count'],
        );
        /* Excel 友好的 CSV：字段里有逗号/引号/换行就加引号 */
        foreach ($line as $i => $v) {
            if (strpbrk((string)$v, ",\"\r\n") !== false) {
                $line[$i] = '"' . str_replace('"', '""', (string)$v) . '"';
            }
        }
        echo implode(',', $line) . "\n";
    }
    $offset += count($rows);
}
exit;
