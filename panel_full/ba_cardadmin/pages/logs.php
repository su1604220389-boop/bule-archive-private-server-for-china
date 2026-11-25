<?php
/**
 * pages/logs.php — 登录日志
 *
 * 两个来源：
 *   1) 从 sdk.log 解析（只读！绝不修改该文件）-> login_logs 表
 *   2) 平台自己记的（登录后台等，source=panel）
 * 列表从 login_logs 读，分页 + 按卡密/设备/结果筛选。
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';

require_login();

$log_path = (string)setting_get('sdk_log_path', SDK_LOG_PATH);

/* ---------------------------------------------------------- 导入 sdk.log --- */
function logs_refresh_card_stats($keys)
{
    $keys = array_values(array_unique(array_filter(array_map('strval', (array)$keys), 'strlen')));
    if (!$keys) {
        return 0;
    }
    $n = 0;
    foreach (array_chunk($keys, 200) as $chunk) {
        $ph = implode(',', array_fill(0, count($chunk), '?'));
        db_run(
            'UPDATE cards c
               JOIN (SELECT card_key, COUNT(*) AS cnt, MAX(ts) AS mts
                       FROM login_logs
                      WHERE result = \'ok\' AND card_key IN (' . $ph . ')
                      GROUP BY card_key) x
                 ON x.card_key = c.card_key
                SET c.login_count  = x.cnt,
                    c.last_login_at = FROM_UNIXTIME(x.mts)',
            $chunk
        );
        db_run(
            'UPDATE cards
                SET last_login_device = (SELECT device_id FROM login_logs l
                                          WHERE l.card_key = cards.card_key AND l.result = \'ok\'
                                          ORDER BY l.ts DESC, l.id DESC LIMIT 1)
              WHERE card_key IN (' . $ph . ')',
            $chunk
        );
        $n += count($chunk);
    }
    return $n;
}

function logs_import_entries($entries, $source_hint = 'sdk.log')
{
    $res = array('added' => 0, 'dup' => 0, 'old' => 0, 'keys' => array());
    if (!$entries) {
        return $res;
    }
    $max_ts = (int)db_val(
        "SELECT MAX(ts) FROM login_logs WHERE source LIKE 'sdk.log%'", array(), 0
    );
    $cutoff = $max_ts > 3600 ? $max_ts - 3600 : 0;   /* 留 1 小时重叠，靠 hash 去重 */

    $ins = db()->prepare(
        'INSERT IGNORE INTO login_logs (card_key, device_id, result, source, ts, raw, line_hash)
         VALUES (?, ?, ?, ?, ?, ?, ?)'
    );

    foreach ($entries as $en) {
        $ts = (int)$en['ts'];
        if ($cutoff > 0 && $ts < $cutoff) {
            $res['old']++;
            continue;
        }
        $raw  = substr((string)$en['raw'], 0, 500);
        $hash = md5($ts . '|' . (string)$en['source'] . '|' . $raw);
        $ins->execute(array(
            substr((string)$en['card'], 0, 64),
            substr((string)$en['device'], 0, 64),
            in_array($en['result'], array('ok', 'reject', 'expired', 'device_limit'), true) ? $en['result'] : 'ok',
            substr((string)$en['source'], 0, 32),
            $ts,
            $raw,
            $hash,
        ));
        if ($ins->rowCount() > 0) {
            $res['added']++;
            if ((string)$en['card'] !== '' && $en['result'] === 'ok') {
                $res['keys'][(string)$en['card']] = true;
            }
        } else {
            $res['dup']++;
        }
    }
    return $res;
}

/* ------------------------------------------------------------------ POST --- */
if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    require_post_csrf();
    $act = post_q('action');
    if ($act === 'parse') {
        $parsed = parse_sdk_log($log_path, 2097152);
        if ($parsed['err'] !== '') {
            flash_set('解析失败：' . $parsed['err'], 'err');
        } else {
            try {
                $r = logs_import_entries($parsed['entries']);
                logs_refresh_card_stats(array_keys($r['keys']));
                $msg = '解析完成：文件 ' . $parsed['lines'] . ' 行，识别 ' . $parsed['recognized']
                     . ' 行，格式不符跳过 ' . $parsed['skipped'] . ' 行；入库 ' . $r['added']
                     . ' 条，重复 ' . $r['dup'] . ' 条，过旧跳过 ' . $r['old'] . ' 条';
                setting_set('log_parse_at', time());
                setting_set('log_parse_lines', $parsed['lines']);
                setting_set('log_parse_skipped', $parsed['skipped']);
                setting_set('log_parse_added', $r['added']);
                audit_log('log.parse', 'sdk.log', $msg);
                flash_set($msg, 'ok');
            } catch (Throwable $e) {
                flash_set('入库失败：' . $e->getMessage(), 'err');
            }
        }
    } elseif ($act === 'clear_old') {
        $days = post_int('days', 30, 1, 3650);
        $st = db_run('DELETE FROM login_logs WHERE ts < ?', array(time() - $days * 86400));
        audit_log('log.clear', 'login_logs', '删除 ' . $days . ' 天前共 ' . $st->rowCount() . ' 条');
        flash_set('已清理 ' . $days . ' 天前的日志 ' . $st->rowCount() . ' 条', 'ok');
    }
    redirect_self();
}

/* ------------------------------------------------------------------ 查询 --- */
$card_id = get_int('card_id', 0, 0);
$q       = trim(get_q('q'));
$device  = trim(get_q('device'));
$result  = get_q('result', 'all');
if (!in_array($result, array('all', 'ok', 'reject', 'expired', 'device_limit'), true)) {
    $result = 'all';
}
$per = get_int('per', 50);
if (!in_array($per, array(50, 100, 200), true)) {
    $per = 50;
}
$page = get_int('page', 1, 1);

$card_key_filter = '';
if ($card_id > 0) {
    $card_key_filter = (string)db_val('SELECT card_key FROM cards WHERE id = ?', array($card_id), '');
}

$where  = array('1=1');
$params = array();
if ($q !== '') {
    $where[]  = 'card_key LIKE ?';
    $params[] = '%' . like_escape($q) . '%';
}
if ($card_key_filter !== '') {
    $where[]  = 'card_key = ?';
    $params[] = $card_key_filter;
}
if ($device !== '') {
    $where[]  = 'device_id LIKE ?';
    $params[] = '%' . like_escape($device) . '%';
}
if ($result !== 'all') {
    $where[]  = 'result = ?';
    $params[] = $result;
}
$wsql  = implode(' AND ', $where);
$total = (int)db_val('SELECT COUNT(*) FROM login_logs WHERE ' . $wsql, $params, 0);
$pages = max(1, (int)ceil($total / $per));
if ($page > $pages) {
    $page = $pages;
}
$offset = ($page - 1) * $per;

$rows = array();
if ($total > 0) {
    $rows = db_all(
        'SELECT * FROM login_logs WHERE ' . $wsql . ' ORDER BY ts DESC, id DESC'
        . ' LIMIT ' . (int)$per . ' OFFSET ' . (int)$offset,
        $params
    );
}

/* 文件状态 */
$file_info = array(
    'path' => $log_path, 'exists' => is_file($log_path), 'readable' => is_readable($log_path),
    'size' => is_file($log_path) ? (int)@filesize($log_path) : 0,
    'mtime' => is_file($log_path) ? (int)@filemtime($log_path) : 0,
);
$show_raw = get_q('raw') === '1';

page_header('登录日志', 'logs');
?>

<div class="toolbar">
  <form method="get" action="<?php echo e(u('pages/logs.php')); ?>" class="filters">
    <input type="text" name="q" value="<?php echo e($q); ?>" placeholder="卡密（部分匹配）" maxlength="64">
    <input type="text" name="device" value="<?php echo e($device); ?>" placeholder="设备 ID（部分匹配）" maxlength="64">
    <select name="result">
      <option value="all"<?php echo $result === 'all' ? ' selected' : ''; ?>>全部结果</option>
      <option value="ok"<?php echo $result === 'ok' ? ' selected' : ''; ?>>成功</option>
      <option value="reject"<?php echo $result === 'reject' ? ' selected' : ''; ?>>卡密错误</option>
      <option value="expired"<?php echo $result === 'expired' ? ' selected' : ''; ?>>已过期</option>
      <option value="device_limit"<?php echo $result === 'device_limit' ? ' selected' : ''; ?>>设备超限</option>
    </select>
    <select name="per">
      <?php foreach (array(50, 100, 200) as $pv) { ?>
        <option value="<?php echo $pv; ?>"<?php echo $per === $pv ? ' selected' : ''; ?>>每页 <?php echo $pv; ?></option>
      <?php } ?>
    </select>
    <?php if ($card_id > 0) { ?><input type="hidden" name="card_id" value="<?php echo (int)$card_id; ?>"><?php } ?>
    <button type="submit" class="btn btn-sm">筛选</button>
    <a class="btn btn-sm" href="<?php echo e(u('pages/logs.php')); ?>">重置</a>
  </form>
  <div class="toolbar-right">
    <form method="post" action="<?php echo e(u('pages/logs.php')); ?>" class="inline">
      <?php echo csrf_field(); ?>
      <input type="hidden" name="action" value="parse">
      <button type="submit" class="btn btn-sm btn-primary">解析 sdk.log 入库</button>
    </form>
    <a class="btn btn-sm" href="<?php echo e(url_with(array('raw' => $show_raw ? '0' : '1'))); ?>">
      <?php echo $show_raw ? '收起原始日志' : '看原始日志尾部'; ?>
    </a>
  </div>
</div>

<?php if ($card_key_filter !== '') { ?>
  <?php echo alert_box('只显示卡密 ' . mask_card($card_key_filter) . ' 的日志', 'info'); ?>
<?php } ?>

<div class="cols">
  <section class="card">
    <div class="card-h"><h2>sdk.log 状态（只读解析，不会改动文件）</h2></div>
    <table class="kv">
      <tr><th>路径</th><td><code class="small"><?php echo e($file_info['path']); ?></code></td></tr>
      <tr><th>文件</th><td>
        <?php if (!$file_info['exists']) { ?>
          <span class="bad">不存在</span>
          <span class="muted small">（如果 sdkcard.py 还没跑过，或者路径配错了）</span>
        <?php } elseif (!$file_info['readable']) { ?>
          <span class="bad">存在但 PHP 用户无权读取</span>
          <span class="muted small">（把 www 用户加进 root 组不是好主意；可以让 cron 以 root 解析，或 chmod 644）</span>
        <?php } else { ?>
          <span class="ok">可读</span> · <?php echo e(bytes_human($file_info['size'])); ?>
          · mtime <?php echo e(fmt_ts($file_info['mtime'])); ?>
        <?php } ?>
      </td></tr>
      <tr><th>上次解析</th><td>
        <?php $pa = setting_int('log_parse_at', 0); ?>
        <?php if ($pa <= 0) { ?><span class="muted">从未解析</span>
        <?php } else { ?>
          <?php echo e(fmt_ts($pa)); ?>
          <span class="muted small">（行 <?php echo (int)setting_int('log_parse_lines', 0); ?>
            · 跳过 <?php echo (int)setting_int('log_parse_skipped', 0); ?>
            · 入库 <?php echo (int)setting_int('log_parse_added', 0); ?>）</span>
        <?php } ?>
      </td></tr>
      <tr><th>失败次数统计</th><td>
        <?php
        $cnt_ok = (int)db_val("SELECT COUNT(*) FROM login_logs WHERE result='ok'", array(), 0);
        $cnt_rj = (int)db_val("SELECT COUNT(*) FROM login_logs WHERE result='reject'", array(), 0);
        ?>
        成功 <?php echo number_format($cnt_ok); ?> · 卡密错误 <?php echo number_format($cnt_rj); ?>
      </td></tr>
    </table>
    <p class="muted small">
      sdk.log 的行只有 <code>HH:MM:SS</code> 没有日期，导入时用文件修改时间做日期锚点。
      导入有去重（同一条不会重复入库），但跨天重新解析历史行时可能补进少量重复，属已知限制。
    </p>
    <form method="post" action="<?php echo e(u('pages/logs.php')); ?>" class="inline"
          onsubmit="return confirm('确认清理？只删数据库里的日志记录，不动 sdk.log。');">
      <?php echo csrf_field(); ?>
      <input type="hidden" name="action" value="clear_old">
      <label class="small muted">清理 <input type="number" name="days" value="30" min="1" max="3650"
        style="width:70px"> 天前</label>
      <button type="submit" class="btn btn-sm btn-danger">清理旧日志</button>
    </form>
  </section>

  <?php if ($show_raw) { ?>
  <section class="card">
    <div class="card-h"><h2>sdk.log 尾部 100 行</h2></div>
    <?php
    $tail = '';
    if ($file_info['readable']) {
        $fp = @fopen($log_path, 'rb');
        if ($fp) {
            $sz = $file_info['size'];
            $start = max(0, $sz - 20000);
            if ($start > 0) {
                @fseek($fp, $start);
            }
            $tail = (string)@stream_get_contents($fp);
            @fclose($fp);
            $arr = explode("\n", trim($tail));
            $arr = array_slice($arr, -100);
            $tail = implode("\n", $arr);
        }
    }
    ?>
    <pre class="code" style="max-height:420px;overflow:auto"><?php echo e($tail === '' ? '（读不到内容）' : $tail); ?></pre>
  </section>
  <?php } ?>
</div>

<?php echo pagination($page, $per, $total, array(), 'pages/logs.php'); ?>

<div class="table-wrap">
<table class="tbl">
  <thead>
    <tr><th class="nowrap">时间</th><th>卡密</th><th>设备</th><th>结果</th><th>来源</th><th>原始行</th></tr>
  </thead>
  <tbody>
  <?php if (!$rows) { ?>
    <tr><td colspan="6" class="empty">
      还没有日志。点上方「解析 sdk.log 入库」把历史日志导进来。
    </td></tr>
  <?php } ?>
  <?php foreach ($rows as $r) {
      $res = (string)$r['result'];
      ?>
    <tr>
      <td class="nowrap"><?php echo e(fmt_ts((int)$r['ts'])); ?><div class="muted small"><?php echo e(date('H:i:s', (int)$r['ts'])); ?></div></td>
      <td><code><?php echo e(mask_card((string)$r['card_key'])); ?></code></td>
      <td><code class="small"><?php echo e(str_limit((string)$r['device_id'], 24)); ?></code></td>
      <td>
        <?php
        if ($res === 'ok') {
            echo '<span class="tag tag-ok">成功</span>';
        } elseif ($res === 'reject') {
            echo '<span class="tag tag-err">卡密错误</span>';
        } elseif ($res === 'expired') {
            echo '<span class="tag tag-warn">已过期</span>';
        } else {
            echo '<span class="tag tag-warn">设备超限</span>';
        }
        ?>
      </td>
      <td class="muted small"><?php echo e((string)$r['source']); ?></td>
      <td class="muted small"><code class="small"><?php echo e(str_limit((string)$r['raw'], 60)); ?></code></td>
    </tr>
  <?php } ?>
  </tbody>
</table>
</div>

<?php echo pagination($page, $per, $total, array(), 'pages/logs.php'); ?>

<?php page_footer(); ?>
