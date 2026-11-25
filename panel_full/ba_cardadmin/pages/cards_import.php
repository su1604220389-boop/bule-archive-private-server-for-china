<?php
/**
 * pages/cards_import.php — 文本批量导入（一行一个卡密），可选统一到期时间
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';

require_login();

$result   = null;
$errors   = array();
$warnings = array();

/** 导入用的卡密宽松校验：可见 ASCII，不含引号/反斜杠/逗号/空白，长度 1-64 */
function import_key_ok($k)
{
    $k = (string)$k;
    if ($k === '' || strlen($k) > 64) {
        return false;
    }
    if (preg_match('/[\s"\\\\,]/', $k)) {
        return false;
    }
    return (bool)preg_match('/^[\x21-\x7E]+$/', $k);
}

/**
 * [CLIENTFMT 2026-11-18] 这张卡密客户端能不能用来登录。
 *
 * 客户端侧的限制（真机实测，改不了）：输入框 maxLength=11 + 数字键盘 +
 * classes.dex 里就是 /^1[0-9]{10}$/。所以除「1 开头 + 10 位数字」之外，
 * 任何格式导进去，玩家输入后都只会看到"卡密错误"。
 *
 * 注意：这里**只用于提示**，导入逻辑仍然按 import_key_ok() 的宽松规则走
 *      （不合法格式照样入库，只是会在结果页被标出来）。
 */
function import_key_client_ok($k)
{
    return (bool)preg_match('/^1[0-9]{10}$/', (string)$k);
}

if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    require_post_csrf();

    /* 大请求保护：超过 post_max_size 时 $_POST 会变空 */
    $clen = isset($_SERVER['CONTENT_LENGTH']) ? (int)$_SERVER['CONTENT_LENGTH'] : 0;
    if (count($_POST) === 0 && $clen > 0) {
        $errors[] = '提交内容过大（' . bytes_human($clen) . '），可能超过 php.ini 的 post_max_size。'
                  . '请分批导入（每次 ≤ 2 MB）';
    }

    $text = post_q('text');
    $fromfile = '';

    /* 可选上传 .txt / .csv（≤ 2 MB） */
    if (!$errors && isset($_FILES['file']) && is_array($_FILES['file'])
        && isset($_FILES['file']['error']) && (int)$_FILES['file']['error'] !== UPLOAD_ERR_NO_FILE) {
        $f = $_FILES['file'];
        if ((int)$f['error'] !== UPLOAD_ERR_OK) {
            $errors[] = '上传失败，错误码 ' . (int)$f['error'];
        } elseif ((int)$f['size'] > MAX_UPLOAD_BYTES) {
            $errors[] = '上传文件超过 ' . bytes_human(MAX_UPLOAD_BYTES) . ' 上限';
        } elseif (!is_uploaded_file($f['tmp_name'])) {
            $errors[] = '上传文件校验失败';
        } else {
            $raw = @file_get_contents($f['tmp_name']);
            if ($raw === false) {
                $errors[] = '读取上传文件失败';
            } else {
                /* 去 BOM */
                if (substr($raw, 0, 3) === "\xEF\xBB\xBF") {
                    $raw = substr($raw, 3);
                }
                $fromfile = (string)$raw;
            }
        }
    }

    $all_text = trim($text) !== '' ? $text : $fromfile;
    if (!$errors && trim((string)$all_text) === '') {
        $errors[] = '请粘贴卡密或上传 txt/csv 文件';
    }
    if (!$errors && strlen((string)$all_text) > MAX_UPLOAD_BYTES) {
        $errors[] = '文本超过 ' . bytes_human(MAX_UPLOAD_BYTES) . ' 上限，请分批导入';
    }

    if (!$errors) {
        $lines = norm_lines((string)$all_text);
        if (count($lines) > 20000) {
            $warnings[] = '一次最多导入 20000 行，已截断';
            $lines = array_slice($lines, 0, 20000);
        }

        /* 统一到期时间 */
        $never  = post_q('never') === '1';
        $expire = $never ? 0 : parse_local_dt(post_q('expire_at'));
        $days   = post_int('days', 0, 0, 36500);
        if (!$never && $expire <= 0 && $days > 0) {
            $expire = time() + $days * 86400;
        }
        $bind_one = post_q('bind_one') === '1' ? 1 : 0;
        $status   = post_q('status') === 'disabled' ? 'disabled' : 'active';
        $note     = trim(post_q('note'));
        if (slen($note) > 255) {
            $note = ssub($note, 0, 255);
        }

        $cand = array();
        $dup_in_file = 0;
        $invalid = array();
        /* [CLIENTFMT 2026-11-18] 客户端只认 ^1[0-9]{10}$：这里只统计，不拦截 */
        $not_client = array();
        $not_client_total = 0;
        foreach ($lines as $line_no => $line) {
            /* 兼容我们导出的 CSV：只取第一列 */
            if (strpos($line, ',') !== false) {
                $parts = explode(',', $line);
                $first = trim($parts[0]);
                if (import_key_ok($first)) {
                    $line = $first;
                }
            }
            if (!import_key_ok($line)) {
                if (count($invalid) < 30) {
                    $invalid[] = $line;
                }
                continue;
            }
            if (isset($cand[$line])) {
                $dup_in_file++;
                continue;
            }
            $cand[$line] = true;
            if (!import_key_client_ok($line)) {
                $not_client_total++;
                if (count($not_client) < 50) {
                    $not_client[] = array('line' => (int)$line_no + 1, 'key' => $line);
                }
            }
        }
        $keys = array_keys($cand);

        if (!$keys) {
            $errors[] = '没有解析到有效卡密（检查是否每行一个、只含可见字符、长度 ≤64）';
        }

        if (!$errors) {
            /* 已存在的 */
            $exists = array();
            foreach (array_chunk($keys, 400) as $chunk) {
                $ph   = implode(',', array_fill(0, count($chunk), '?'));
                $rows = db_all('SELECT card_key FROM cards WHERE card_key IN (' . $ph . ')', $chunk);
                foreach ($rows as $r) {
                    $exists[(string)$r['card_key']] = true;
                }
            }

            $admin = substr((string)current_admin()['username'], 0, 64);
            $added = 0;
            $ids   = array();
            try {
                db()->beginTransaction();
                $ins = db()->prepare(
                    'INSERT INTO cards (card_key, status, expire_at, bind_one, created_at, created_by, note,
                                        login_count, last_login_at, last_login_device)
                     VALUES (?, ?, ?, ?, NOW(), ?, ?, 0, NULL, NULL)'
                );
                foreach ($keys as $k) {
                    if (isset($exists[$k])) {
                        continue;
                    }
                    $ins->execute(array($k, $status, (int)$expire, (int)$bind_one, $admin, $note));
                    $ids[] = (int)db()->lastInsertId();
                    $added++;
                }
                db()->commit();
            } catch (Throwable $e) {
                try {
                    if (db()->inTransaction()) {
                        db()->rollBack();
                    }
                } catch (Throwable $e2) {
                    /* ignore */
                }
                $errors[] = '导入失败（已回滚）：' . $e->getMessage();
                $added = 0;
                $ids   = array();
            }

            if (!$errors) {
                batch_ids_save($ids);
                $result = array(
                    'lines'    => count($lines),
                    'valid'    => count($keys),
                    'added'    => $added,
                    'exists'   => count($keys) - $added,
                    'dup_file' => $dup_in_file,
                    'invalid'  => count($invalid) > 0 ? $invalid : array(),
                    'not_client' => $not_client,
                    'not_client_total' => $not_client_total,
                    'expire'   => $expire,
                );
                audit_log('card.import', '导入 ' . $added . ' 个卡密',
                    '文件行数=' . count($lines) . ' 有效=' . count($keys) . ' 已存在=' . (count($keys) - $added)
                    . ' 文件内重复=' . $dup_in_file . ' expire=' . $expire
                    . ' 客户端不可用=' . $not_client_total);
                if ($added > 0) {
                    flash_set('导入完成：新增 ' . $added . ' 个卡密', 'ok');
                }
            }
        }
    }
}

page_header('批量导入', 'import');
?>

<?php foreach ($errors as $er) { echo alert_box($er, 'err'); } ?>
<?php foreach ($warnings as $w) { echo alert_box($w, 'warn'); } ?>

<?php if ($result) { ?>
<section class="card card-result">
  <div class="card-h"><h2>导入结果</h2>
    <div class="card-h-act">
      <?php if ($result['added'] > 0) { ?>
        <a class="btn btn-sm btn-primary" href="<?php echo e(u('pages/cards.php?batch=last&reveal=1')); ?>">查看刚导入的</a>
        <form method="post" action="<?php echo e(u('pages/cards_export.php')); ?>" class="inline">
          <?php echo csrf_field(); ?>
          <input type="hidden" name="format" value="txt">
          <input type="hidden" name="batch" value="last">
          <button type="submit" class="btn btn-sm">导出 TXT</button>
        </form>
      <?php } ?>
    </div>
  </div>
  <table class="kv">
    <tr><th>文件行数</th><td><?php echo number_format($result['lines']); ?></td></tr>
    <tr><th>有效且唯一</th><td><?php echo number_format($result['valid']); ?></td></tr>
    <tr><th>新增入库</th><td><b class="ok"><?php echo number_format($result['added']); ?></b></td></tr>
    <tr><th>数据库已存在</th><td><?php echo number_format($result['exists']); ?></td></tr>
    <tr><th>文本内重复</th><td><?php echo number_format($result['dup_file']); ?></td></tr>
    <tr><th>客户端不可用</th><td><?php
      $nct = (int)$result['not_client_total'];
      echo $nct > 0 ? '<b class="warn">' . number_format($nct) . '</b>' : '0';
    ?></td></tr>
    <tr><th>统一到期</th><td><?php echo $result['expire'] === 0 ? '永不过期' : e(fmt_ts($result['expire'])); ?></td></tr>
  </table>
  <?php if ($result['invalid']) { ?>
    <p class="muted small">以下行被跳过（非法/含逗号引号等）：</p>
    <pre class="code"><?php foreach ($result['invalid'] as $iv) { echo e(str_limit($iv, 80)) . "\n"; } ?></pre>
  <?php } ?>
  <?php if ((int)$result['not_client_total'] > 0) { ?>
    <?php echo alert_box('有 ' . number_format((int)$result['not_client_total'])
      . ' 个卡密客户端无法登录：客户端只接受「1 开头 + 10 位数字」（^1[0-9]{10}$）。'
      . '这些卡已照常入库，但玩家输入后会提示卡密错误。', 'warn'); ?>
    <p class="muted small">下面列出前 <?php echo count($result['not_client']); ?> 条（行号 / 卡密）：</p>
    <pre class="code"><?php foreach ($result['not_client'] as $nc) {
      echo e('第 ' . $nc['line'] . ' 行  ' . str_limit($nc['key'], 80)) . "\n";
    } ?></pre>
  <?php } ?>
</section>
<?php } ?>

<section class="card">
  <div class="card-h"><h2>粘贴导入</h2></div>
  <form method="post" action="<?php echo e(u('pages/cards_import.php')); ?>" enctype="multipart/form-data" class="form-grid">
    <?php echo csrf_field(); ?>

    <label class="fld fld-wide"><span>卡密文本（一行一个）</span>
      <textarea name="text" rows="12" class="code-area"
                placeholder="11111111111&#10;12222222222&#10;<REDACTED_CONTACT>"></textarea>
      <em>支持直接粘贴我们导出的 TXT/CSV（CSV 只取第一列）；上限 <?php echo e(bytes_human(MAX_UPLOAD_BYTES)); ?></em>
      <em><b>注意：客户端只接受「1 开头 + 10 位数字」，其它格式（含旧的 16 位卡）导进去玩家无法登录 ——
        不会被拒绝，但会在导入结果里被标出来。</b></em>
    </label>

    <label class="fld fld-wide"><span>或者上传文件（.txt / .csv）</span>
      <input type="file" name="file" accept=".txt,.csv,text/plain,text/csv">
      <em>上传了文件就用文件内容，忽略上面的粘贴框；≤ <?php echo e(bytes_human(MAX_UPLOAD_BYTES)); ?></em>
    </label>

    <label class="fld"><span>统一有效期（天）</span>
      <input type="number" name="days" value="0" min="0" max="36500">
      <em>0 = 永不过期</em>
    </label>

    <label class="fld"><span>统一到期时间（可选）</span>
      <input type="datetime-local" name="expire_at" value="">
    </label>

    <label class="fld fld-check">
      <input type="checkbox" name="never" value="1" checked>
      <span>永不过期</span>
    </label>

    <label class="fld fld-check">
      <input type="checkbox" name="bind_one" value="1" checked>
      <span>只允许绑定一台设备</span>
    </label>

    <label class="fld"><span>导入后状态</span>
      <select name="status">
        <option value="active">启用（立即生效）</option>
        <option value="disabled">禁用（先入库不生效）</option>
      </select>
    </label>

    <label class="fld fld-wide"><span>备注（可选）</span>
      <input type="text" name="note" value="" maxlength="255" placeholder="比如：导入批次 A">
    </label>

    <div class="fld fld-wide fld-actions">
      <button type="submit" class="btn btn-primary">开始导入</button>
      <span class="muted small">重复的卡密会自动跳过，不会覆盖已有数据</span>
    </div>
  </form>
</section>

<?php page_footer(); ?>
