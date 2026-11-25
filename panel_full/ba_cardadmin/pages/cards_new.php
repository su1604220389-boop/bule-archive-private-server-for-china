<?php
/**
 * pages/cards_new.php — 新建卡密（单个 / 批量生成）
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';

require_login();

/* 卡密格式固定：客户端只认 ^1\d{10}$（1 开头 + 共 11 位数字）。
   长度 / 前缀 / 字符集全部不可配，原因见 inc/helpers.php 的 gen_card_key()。 */

$errors = array();

/* ----------------------------------------------------------------- POST --- */
if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    require_post_csrf();
    $act = post_q('action');

    /* ---- 单个创建 ---- */
    if ($act === 'single') {
        $key      = trim(post_q('card_key'));
        $never    = post_q('never') === '1';
        $expire   = $never ? 0 : parse_local_dt(post_q('expire_at'));
        $days     = post_int('days', 0, 0, 36500);
        if (!$never && $expire <= 0 && $days > 0) {
            $expire = time() + $days * 86400;
        }
        $kind     = card_kind_norm(post_q('kind', 'paid'));
        $maxd     = card_max_devices_norm($kind, post_int('max_devices', 0, 0, 9999));
        $bind_one = card_bind_one_from_max($maxd);   /* legacy 派生，仅兼容旧逻辑 */
        $note     = trim(post_q('note'));
        if (slen($note) > 255) {
            $note = ssub($note, 0, 255);
        }

        if ($key === '') {
            /* 固定 1 + 10 位数字；生成后查库，冲突最多重试 10 次，仍冲突就报错 */
            try {
                $key = gen_card_key_unique(10);
            } catch (Throwable $e) {
                $errors[] = $e->getMessage();
            }
        } else {
            if (!preg_match('/^[A-Za-z0-9_\-\.]{4,64}$/', $key)) {
                $errors[] = '自定义卡密只能是 4-64 位的字母/数字/下划线/减号/点';
            } elseif (!card_key_is_client_compatible($key) && post_q('allow_non_client') !== '1') {
                $errors[] = '客户端只接受 1 开头的 11 位数字（例如 12345678901），'
                          . '这张卡 ' . mask_card($key) . ' 在客户端输不进去。'
                          . '确实要建这种卡的话，请先勾选「我知道这张卡客户端登不上」';
            }
        }

        if (!$errors) {
            try {
                $dup = (int)db_val('SELECT COUNT(*) FROM cards WHERE card_key = ?', array($key), 0);
                if ($dup > 0) {
                    $errors[] = '卡密已存在：' . mask_card($key);
                } else {
                    db_run(
                        'INSERT INTO cards (card_key, status, expire_at, bind_one, kind, max_devices,
                                            created_at, created_by, note, login_count, last_login_at, last_login_device)
                         VALUES (?, ?, ?, ?, ?, ?, NOW(), ?, ?, 0, NULL, NULL)',
                        array($key, 'active', (int)$expire, (int)$bind_one, $kind, (int)$maxd,
                              substr((string)current_admin()['username'], 0, 64), $note)
                    );
                    $new_id = db_insert_id();
                    batch_ids_save(array($new_id));
                    audit_log('card.create', mask_card($key),
                        'id=' . $new_id . ' expire=' . $expire . ' kind=' . $kind
                        . ' max_devices=' . $maxd . ' bind_one=' . $bind_one);
                    flash_set('已创建卡密：' . $key . '（复制保存好，随时可在列表再复制）', 'ok');
                    redirect('pages/cards_new.php?show=last');
                }
            } catch (Throwable $e) {
                $errors[] = '创建失败：' . $e->getMessage();
            }
        }
    }

    /* ---- 批量生成 ---- */
    if ($act === 'batch') {
        $qty     = post_int('qty', 10, 1, MAX_BATCH_GEN);
        $never   = post_q('never') === '1';
        $expire  = $never ? 0 : parse_local_dt(post_q('expire_at'));
        $days    = post_int('days', 0, 0, 36500);
        $note    = trim(post_q('note'));
        $kind    = card_kind_norm(post_q('kind', 'paid'));
        $maxd    = card_max_devices_norm($kind, post_int('max_devices', 0, 0, 9999));
        $bind_one = card_bind_one_from_max($maxd);   /* legacy 派生 */

        if (!$never && $expire <= 0 && $days > 0) {
            $expire = time() + $days * 86400;
        }
        if (slen($note) > 255) {
            $note = ssub($note, 0, 255);
        }
        /* 格式固定：1 + 10 位数字（客户端正则 ^1\d{10}$ 硬编码在 dex 里，改不了） */
        $len     = 11;

        if (!$errors) {
            try {
                $made   = array();
                $seen   = array();
                $tries  = 0;
                $max_try = $qty * 40 + 200;
                while (count($made) < $qty && $tries < $max_try) {
                    $tries++;
                    try {
                        $k = gen_card_key_unique(10);   /* 生成即查库，冲突重试 ≤10 次 */
                    } catch (Throwable $e) {
                        $errors[] = $e->getMessage();
                        break;
                    }
                    if (isset($seen[$k])) {
                        continue;
                    }
                    $seen[$k] = true;
                    $made[]   = $k;
                }

                /* 去掉数据库里已存在的 */
                $exists = array();
                foreach (array_chunk($made, 400) as $chunk) {
                    $ph   = implode(',', array_fill(0, count($chunk), '?'));
                    $rows = db_all('SELECT card_key FROM cards WHERE card_key IN (' . $ph . ')', $chunk);
                    foreach ($rows as $rr) {
                        $exists[(string)$rr['card_key']] = true;
                    }
                }
                $final = array();
                foreach ($made as $k) {
                    if (!isset($exists[$k])) {
                        $final[] = $k;
                    }
                }
                if (!$errors && count($final) < $qty) {
                    /* 生成器已逐张查库；走到这里说明冲突异常，能生成多少算多少并报错 */
                    $errors[] = '可生成的唯一卡密不足：目标 ' . $qty . ' 个，实际可用 ' . count($final)
                              . ' 个（请减少数量或稍后重试）';
                }

                $admin  = substr((string)current_admin()['username'], 0, 64);
                $ids    = array();
                if (!$errors) {
                    db()->beginTransaction();
                    $ins = db()->prepare(
                        'INSERT INTO cards (card_key, status, expire_at, bind_one, kind, max_devices,
                                            created_at, created_by, note, login_count, last_login_at, last_login_device)
                         VALUES (?, ?, ?, ?, ?, ?, NOW(), ?, ?, 0, NULL, NULL)'
                    );
                    foreach ($final as $k) {
                        $ins->execute(array($k, 'active', (int)$expire, (int)$bind_one, $kind, (int)$maxd, $admin, $note));
                        $ids[] = (int)db()->lastInsertId();
                    }
                    db()->commit();

                    batch_ids_save($ids);
                    $exp_txt = ((int)$expire === 0) ? '永不过期' : ('有效期至 ' . fmt_ts($expire));
                    audit_log('card.batch_create', '批量生成 ' . count($ids) . ' 个卡密',
                        'len=' . $len . ' format=^1\d{10}$'
                        . ' expire=' . $expire . ' kind=' . $kind . ' max_devices=' . $maxd
                        . ' bind_one=' . $bind_one);
                    flash_set('批量生成成功：' . count($ids) . ' 个卡密（' . $exp_txt . '）', 'ok');
                    redirect('pages/cards_new.php?show=last');
                }
            } catch (Throwable $e) {
                try {
                    if (db()->inTransaction()) {
                        db()->rollBack();
                    }
                } catch (Throwable $e2) {
                    /* ignore */
                }
                $errors[] = '批量生成失败：' . $e->getMessage();
            }
        }
    }
}

/* ------------------------------------------------------------ 展示最近一批 --- */
$show = get_q('show');
$show_ids = array();
$show_keys = array();
if ($show === 'last') {
    $show_ids = batch_ids_load();
    if ($show_ids) {
        foreach (array_chunk($show_ids, 400) as $chunk) {
            $ph   = implode(',', array_fill(0, count($chunk), '?'));
            $rows = db_all('SELECT id, card_key, expire_at FROM cards WHERE id IN (' . $ph . ') ORDER BY id ASC', $chunk);
            foreach ($rows as $r) {
                $show_keys[] = array(
                    'id' => (int)$r['id'],
                    'key' => (string)$r['card_key'],
                    'expire' => (int)$r['expire_at'],
                );
            }
        }
    }
}

page_header('新建卡密', 'new');
?>

<?php foreach ($errors as $er) { echo alert_box($er, 'err'); } ?>

<div class="card" style="padding:10px 14px;margin-bottom:12px">
  <b>卡类型怎么选？</b><br>
  <span class="muted small">公益卡：账号绑定在当前设备上，换设备就是新账号；不限设备数。</span><br>
  <span class="muted small">付费卡：账号跟随这张卡；最多可绑 N 台设备（0 表示不限），可随时调整。</span>
</div>

<?php if ($show_keys) { ?>
<section class="card card-result" id="batch-result">
  <div class="card-h">
    <h2>刚生成 / 刚创建的 <?php echo count($show_keys); ?> 个卡密</h2>
    <div class="card-h-act">
      <button type="button" class="btn btn-sm btn-primary" id="ca-copy-all">一键复制全部</button>
      <form method="post" action="<?php echo e(u('pages/cards_export.php')); ?>" class="inline">
        <?php echo csrf_field(); ?>
        <input type="hidden" name="format" value="txt">
        <input type="hidden" name="batch" value="last">
        <button type="submit" class="btn btn-sm">导出 TXT</button>
      </form>
      <form method="post" action="<?php echo e(u('pages/cards_export.php')); ?>" class="inline">
        <?php echo csrf_field(); ?>
        <input type="hidden" name="format" value="csv">
        <input type="hidden" name="batch" value="last">
        <button type="submit" class="btn btn-sm">导出 CSV</button>
      </form>
      <a class="btn btn-sm" href="<?php echo e(u('pages/cards.php?batch=last&reveal=1')); ?>">去列表看</a>
    </div>
  </div>
  <textarea id="ca-batch-text" class="code-area" rows="10" readonly><?php
    foreach ($show_keys as $k) {
        echo e($k['key']) . "\n";
    }
  ?></textarea>
  <p class="muted small"><?php echo count($show_keys); ?> 条 · 已自动存入数据库 ·
    到期：<?php echo $show_keys[0]['expire'] === 0 ? '永不过期' : e(fmt_ts($show_keys[0]['expire'])); ?> ·
    导出的 TXT 是一行一个卡密，可直接发号</p>
</section>
<?php } ?>

<div class="cols">
  <section class="card">
    <div class="card-h"><h2>单个新建</h2></div>
    <form method="post" action="<?php echo e(u('pages/cards_new.php')); ?>" class="form-grid">
      <?php echo csrf_field(); ?>
      <input type="hidden" name="action" value="single">

      <label class="fld"><span>卡密（留空 = 自动生成）</span>
        <input type="text" name="card_key" value="" maxlength="64"
               placeholder="11 位数字，如 12345678901；留空自动生成">
        <em>客户端只接受 <b>1 开头的 11 位数字</b>，例如 12345678901（输入框 maxLength=11 + 数字键盘 + 正则 ^1\d{10}$ 全部硬编码在 dex 里，改不了）</em>
      </label>

      <label class="fld fld-check fld-wide">
        <input type="checkbox" name="allow_non_client" value="1">
        <span>我知道这张卡客户端登不上（仍要创建非「1 开头 11 位数字」的卡密）</span>
      </label>

      <label class="fld"><span>有效期（天）</span>
        <input type="number" name="days" value="30" min="0" max="36500">
        <em>0 = 永不过期；填了下面的具体到期时间则以到期时间为准</em>
      </label>

      <label class="fld"><span>具体到期时间（可选）</span>
        <input type="datetime-local" name="expire_at" value="">
      </label>

      <label class="fld fld-check">
        <input type="checkbox" name="never" value="1">
        <span>永不过期</span>
      </label>

      <label class="fld"><span>卡类型</span>
        <select name="kind">
          <option value="paid" selected>付费卡（账号跟随卡密）</option>
          <option value="free">公益卡（账号跟随设备）</option>
        </select>
        <em>建好后不可修改（改类型会让该卡下所有设备永久失联）</em>
      </label>

      <label class="fld"><span>最大设备数</span>
        <input type="number" name="max_devices" value="0" min="0" max="9999">
        <em>0 = 不限；1 = 最多一台；N = 最多 N 台。公益卡固定不限（选公益后自动置灰）。</em>
      </label>

      <label class="fld fld-wide"><span>备注（可选）</span>
        <input type="text" name="note" value="" maxlength="255" placeholder="比如：某客户/某批次">
      </label>

      <div class="fld fld-wide fld-actions">
        <button type="submit" class="btn btn-primary">创建</button>
      </div>
    </form>
  </section>

  <section class="card" id="batch">
    <div class="card-h"><h2>批量生成（≤ <?php echo (int)MAX_BATCH_GEN; ?> 个）</h2></div>
    <form method="post" action="<?php echo e(u('pages/cards_new.php')); ?>" class="form-grid">
      <?php echo csrf_field(); ?>
      <input type="hidden" name="action" value="batch">

      <label class="fld"><span>数量</span>
        <input type="number" name="qty" value="100" min="1" max="<?php echo (int)MAX_BATCH_GEN; ?>" required>
      </label>

      <div class="fld fld-wide">
        <span>卡密格式（固定，不可选）</span>
        <input type="text" value="1 开头 + 10 位数字，共 11 位（例如 12345678901）" readonly>
        <em>客户端输入框 maxLength=11 + 数字键盘 + 正则 ^1\d{10}$ 全部硬编码在 dex 里，改不了；
            长度 / 前缀 / 字符集已移除，避免再发出客户端登不上的卡。</em>
      </div>

      <label class="fld"><span>有效期（天）</span>
        <input type="number" name="days" value="30" min="0" max="36500">
        <em>0 = 永不过期</em>
      </label>

      <label class="fld"><span>具体到期时间（可选）</span>
        <input type="datetime-local" name="expire_at" value="">
      </label>

      <label class="fld fld-check">
        <input type="checkbox" name="never" value="1">
        <span>永不过期</span>
      </label>

      <label class="fld"><span>卡类型</span>
        <select name="kind">
          <option value="paid" selected>付费卡（账号跟随卡密）</option>
          <option value="free">公益卡（账号跟随设备）</option>
        </select>
        <em>建好后不可修改（改类型会让该卡下所有设备永久失联）</em>
      </label>

      <label class="fld"><span>最大设备数</span>
        <input type="number" name="max_devices" value="0" min="0" max="9999">
        <em>0 = 不限；1 = 最多一台；N = 最多 N 台。公益卡固定不限（选公益后自动置灰）。</em>
      </label>

      <label class="fld fld-wide"><span>备注（可选）</span>
        <input type="text" name="note" value="" maxlength="255" placeholder="比如：某批次/某客户">
      </label>

      <div class="fld fld-wide fld-actions">
        <button type="submit" class="btn btn-primary">开始生成</button>
        <span class="muted small">生成后立刻显示 + 一键复制 + 一键导出</span>
      </div>
    </form>
  </section>
</div>

<script>
document.addEventListener('DOMContentLoaded', function () {
  /* 卡类型联动：选「公益」时设备数置灰并清零 */
  Array.prototype.forEach.call(document.querySelectorAll('form'), function (f) {
    var k = f.querySelector('select[name="kind"]');
    var m = f.querySelector('input[name="max_devices"]');
    if (!k || !m) { return; }
    function syncKind() {
      var free = (k.value === 'free');
      m.disabled = free;
      if (free) { m.value = '0'; }
      m.title = free ? '公益卡不限设备' : '';
    }
    k.addEventListener('change', syncKind);
    syncKind();
  });
});
</script>

<?php page_footer(); ?>
