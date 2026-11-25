<?php
/**
 * pages/cards.php — 卡密列表：分页/搜索/筛选/批量操作/单个操作/编辑
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';
require_once __DIR__ . '/../inc/players.php';

require_login();

/* ------------------------------------------------------------ AJAX: 取明文 --- */
/* F4：改成 POST + CSRF（原来 GET 可直接被跨站触发/被预取） */
if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST'
    && post_q('ajax') === 'key') {
    verify_csrf();
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    $id  = post_int('id', 0, 1);
    $key = (string)db_val('SELECT card_key FROM cards WHERE id = ?', array($id), '');
    if ($key === '') {
        echo json_encode(array('ok' => false, 'msg' => 'not found'));
        exit;
    }
    audit_log('card.reveal', '卡密 #' . $id, '列表里查看明文');
    echo json_encode(array('ok' => true, 'key' => $key), JSON_UNESCAPED_UNICODE);
    exit;
}

/* ---------------------------------------------------------------- 筛选参数 --- */
$per_list = array(50, 100, 200);
$per      = get_int('per', 50);
if (!in_array($per, $per_list, true)) {
    $per = 50;
}
$page = get_int('page', 1, 1);
$q    = trim(get_q('q'));
if (slen($q) > 64) {
    $q = ssub($q, 0, 64);
}
$status = get_q('status', 'all');
if (!in_array($status, array('all', 'active', 'disabled'), true)) {
    $status = 'all';
}
$exp = get_q('exp', 'all');
if (!in_array($exp, array('all', 'expired', 'soon', 'never'), true)) {
    $exp = 'all';
}
$bind = get_q('bind', 'all');
if (!in_array($bind, array('all', 'bound', 'unbound'), true)) {
    $bind = 'all';
}
$sort = get_q('sort', 'new') === 'old' ? 'old' : 'new';
$reveal = get_int('reveal', 0) === 1;
$batch  = get_q('batch');

/* 当前查询串（POST 后原样返回，保持筛选条件） */
$ret_params = array_filter(array(
    'q'      => $q,
    'status' => $status === 'all' ? '' : $status,
    'exp'    => $exp === 'all' ? '' : $exp,
    'bind'   => $bind === 'all' ? '' : $bind,
    'sort'   => $sort === 'new' ? '' : $sort,
    'per'    => (string)$per === '50' ? '' : (string)$per,
    'page'   => $page > 1 ? (string)$page : '',
    'reveal' => $reveal ? '1' : '',
    'batch'  => $batch === 'last' ? 'last' : '',
));
$ret_qs = http_build_query($ret_params, '', '&');

/* ---------------------------------------------------------------- 批量操作 --- */
function cards_ids_from_post()
{
    $raw = isset($_POST['ids']) && is_array($_POST['ids']) ? $_POST['ids'] : array();
    $ids = array();
    foreach ($raw as $v) {
        $v = (int)$v;
        if ($v > 0) {
            $ids[$v] = $v;
        }
    }
    $ids = array_values($ids);
    if (count($ids) > MAX_BATCH_GEN) {
        $ids = array_slice($ids, 0, MAX_BATCH_GEN);
    }
    return $ids;
}

function cards_in_sql($ids)
{
    return implode(',', array_fill(0, count($ids), '?'));
}

if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    require_post_csrf();
    $act = post_q('action');
    $msg = '';
    $ok  = true;

    try {
        if ($act === 'bulk') {
            $ids = cards_ids_from_post();
            $op  = post_q('op');
            if (!$ids) {
                $ok  = false;
                $msg = '没有勾选任何卡密';
            } else {
                $n = count($ids);
                $ph = cards_in_sql($ids);
                if ($op === 'delete') {
                    db_run('DELETE FROM cards WHERE id IN (' . $ph . ')', $ids);
                    $msg = '已删除 ' . $n . ' 张卡密（其设备绑定随外键级联删除）';
                } elseif ($op === 'extend') {
                    $days = post_int('days', 30, 1, 36500);
                    db_run(
                        'UPDATE cards SET expire_at = CASE WHEN expire_at = 0 THEN 0 ELSE expire_at + ? END
                          WHERE id IN (' . $ph . ')',
                        array_merge(array((int)$days * 86400), $ids)
                    );
                    $msg = '已延期 ' . $n . ' 张卡密 ' . $days . ' 天（永不过期的保持 0）';
                } elseif ($op === 'never') {
                    db_run('UPDATE cards SET expire_at = 0 WHERE id IN (' . $ph . ')', $ids);
                    $msg = '已把 ' . $n . ' 张卡密设为永不过期';
                } elseif ($op === 'unbind') {
                    db_run('DELETE FROM card_devices WHERE card_id IN (' . $ph . ')', $ids);
                    $msg = '已解绑 ' . $n . ' 张卡密的所有设备';
                } elseif ($op === 'enable') {
                    db_run("UPDATE cards SET status = 'active' WHERE id IN (" . $ph . ')', $ids);
                    $msg = '已启用 ' . $n . ' 张卡密';
                } elseif ($op === 'disable') {
                    db_run("UPDATE cards SET status = 'disabled' WHERE id IN (" . $ph . ')', $ids);
                    $msg = '已禁用 ' . $n . ' 张卡密';
                } else {
                    $ok  = false;
                    $msg = '未知批量操作';
                }
                if ($ok) {
                    audit_log('card.bulk_' . $op, $n . ' 张卡密', 'ids=' . implode(',', array_slice($ids, 0, 50))
                        . (count($ids) > 50 ? '…' : '') . ' | ' . $msg);
                }
            }
        } elseif ($act === 'row') {
            $id = post_int('id', 0, 1);
            $op = post_q('op');
            $row = $id > 0 ? db_row('SELECT * FROM cards WHERE id = ?', array($id)) : null;
            if (!$row) {
                $ok  = false;
                $msg = '卡密不存在';
            } elseif ($op === 'delete') {
                db_run('DELETE FROM cards WHERE id = ?', array($id));
                $msg = '已删除卡密 ' . mask_card((string)$row['card_key']);
                audit_log('card.delete', mask_card((string)$row['card_key']), 'id=' . $id);
            } elseif ($op === 'unbind') {
                $st = db_run('DELETE FROM card_devices WHERE card_id = ?', array($id));
                $msg = '已解绑 ' . $st->rowCount() . ' 台设备（' . mask_card((string)$row['card_key']) . '）';
                audit_log('card.unbind', mask_card((string)$row['card_key']), '解绑 ' . $st->rowCount() . ' 台');
            } elseif ($op === 'enable' || $op === 'disable') {
                db_run('UPDATE cards SET status = ? WHERE id = ?',
                    array($op === 'enable' ? 'active' : 'disabled', $id));
                $msg = '卡密已' . ($op === 'enable' ? '启用' : '禁用') . '：' . mask_card((string)$row['card_key']);
                audit_log('card.' . $op, mask_card((string)$row['card_key']), 'id=' . $id);
            } elseif ($op === 'never') {
                db_run('UPDATE cards SET expire_at = 0 WHERE id = ?', array($id));
                $msg = '已设为永不过期：' . mask_card((string)$row['card_key']);
                audit_log('card.never', mask_card((string)$row['card_key']), 'id=' . $id);
            } else {
                $ok  = false;
                $msg = '未知操作';
            }
        } elseif ($act === 'save') {
            $id  = post_int('id', 0, 1);
            $row = $id > 0 ? db_row('SELECT * FROM cards WHERE id = ?', array($id)) : null;
            if (!$row) {
                $ok  = false;
                $msg = '卡密不存在';
            } else {
                $never  = post_q('never') === '1';
                $expire = $never ? 0 : parse_local_dt(post_q('expire_at'));
                if (!$never && $expire <= 0 && trim(post_q('expire_at')) !== '') {
                    $ok  = false;
                    $msg = '到期时间格式不对';
                }
                if ($ok) {
                    /* kind 编辑页只读：一律沿用数据库里的值，不接受 POST 覆盖 */
                    $kind = (isset($row['kind']) && (string)$row['kind'] === 'free') ? 'free' : 'paid';
                    $maxd = card_max_devices_norm($kind, post_int('max_devices', 0, 0, 9999));
                    $bind_one = card_bind_one_from_max($maxd);   /* legacy 派生 */
                    $st       = post_q('status') === 'disabled' ? 'disabled' : 'active';
                    $note     = trim(post_q('note'));
                    if (slen($note) > 255) {
                        $note = ssub($note, 0, 255);
                    }
                    db_run(
                        'UPDATE cards SET expire_at = ?, bind_one = ?, max_devices = ?, status = ?, note = ? WHERE id = ?',
                        array((int)$expire, (int)$bind_one, (int)$maxd, $st, $note, $id)
                    );
                    $msg = '已保存：' . mask_card((string)$row['card_key']);
                    audit_log('card.edit', mask_card((string)$row['card_key']),
                        'expire=' . $expire . ' kind=' . $kind . ' max_devices=' . $maxd
                        . ' bind_one=' . $bind_one . ' status=' . $st);
                }
            }
        } else {
            $ok  = false;
            $msg = '未知操作';
        }
    } catch (Throwable $e) {
        $ok  = false;
        $msg = '操作失败：' . $e->getMessage();
    }

    flash_set($msg, $ok ? 'ok' : 'err');

    /* 回到原来的筛选页 */
    $go = 'pages/cards.php';
    $ret = post_q('ret');
    if ($ret !== '') {
        parse_str($ret, $tmp);
        $keep = array();
        foreach (array('q', 'status', 'exp', 'bind', 'sort', 'per', 'page', 'reveal', 'batch') as $k) {
            if (isset($tmp[$k]) && is_string($tmp[$k]) && $tmp[$k] !== '') {
                $keep[$k] = $tmp[$k];
            }
        }
        if ($keep) {
            $go .= '?' . http_build_query($keep);
        }
    }
    redirect($go);
}

/* ---------------------------------------------------------------- 查询 --- */
$where  = array('1=1');
$params = array();
$now    = time();

if ($q !== '') {
    $where[]  = 'card_key LIKE ?';
    $params[] = '%' . like_escape($q) . '%';
}
if ($status !== 'all') {
    $where[]  = 'status = ?';
    $params[] = $status;
}
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
if ($bind === 'bound') {
    $where[] = 'EXISTS (SELECT 1 FROM card_devices d WHERE d.card_id = cards.id)';
} elseif ($bind === 'unbound') {
    $where[] = 'NOT EXISTS (SELECT 1 FROM card_devices d WHERE d.card_id = cards.id)';
}

$batch_ids = array();
if ($batch === 'last') {
    $batch_ids = batch_ids_load();
    if ($batch_ids) {
        $where[] = 'id IN (' . implode(',', array_fill(0, count($batch_ids), '?')) . ')';
        foreach ($batch_ids as $bid) {
            $params[] = (int)$bid;
        }
    } else {
        $where[] = '1 = 0';
    }
}

$wsql  = implode(' AND ', $where);
$order = $sort === 'old' ? 'created_at ASC, id ASC' : 'created_at DESC, id DESC';

$total = 0;
$rows  = array();
$page_errors = array();
try {
    $total = (int)db_val('SELECT COUNT(*) FROM cards WHERE ' . $wsql, $params, 0);
} catch (Throwable $e) {
    $page_errors[] = '查询失败：' . $e->getMessage();
}
$pages = max(1, (int)ceil($total / $per));
if ($page > $pages) {
    $page = $pages;
}
$offset = ($page - 1) * $per;

if ($total > 0) {
    try {
        $rows = db_all(
            'SELECT * FROM cards WHERE ' . $wsql . ' ORDER BY ' . $order
            . ' LIMIT ' . (int)$per . ' OFFSET ' . (int)$offset,
            $params
        );
    } catch (Throwable $e) {
        $page_errors[] = '查询失败：' . $e->getMessage();
    }
}

/* 设备（一次查完当前页） */
$devmap = array();
/* 卡密 ↔ 玩家 绑定（面板自建表 card_players，缺失时自动建） */
$bindmap = player_card_bindings();
if ($rows) {
    $ids = array();
    foreach ($rows as $r) {
        $ids[] = (int)$r['id'];
    }
    try {
        $dev_rows = db_all(
            'SELECT card_id, device_id, last_seen_at FROM card_devices WHERE card_id IN ('
            . implode(',', array_fill(0, count($ids), '?')) . ') ORDER BY id ASC',
            $ids
        );
        foreach ($dev_rows as $d) {
            $cid = (int)$d['card_id'];
            if (!isset($devmap[$cid])) {
                $devmap[$cid] = array();
            }
            $devmap[$cid][] = $d;
        }
    } catch (Throwable $e) {
        /* ignore */
    }
}

/* 编辑对象 */
$edit = null;
if (get_q('action') === 'edit') {
    $eid = get_int('id', 0, 1);
    if ($eid > 0) {
        $edit = db_row('SELECT * FROM cards WHERE id = ?', array($eid));
        if ($edit && !isset($devmap[(int)$edit['id']])) {
            $d = db_all('SELECT card_id, device_id, last_seen_at FROM card_devices WHERE card_id = ?', array($eid));
            $devmap[(int)$edit['id']] = $d;
        }
    }
}

/* 编辑页的卡类型/设备上限（ALTER 前缺列时按 bind_one 兼容） */
$edit_kind = 'paid';
$edit_maxd = 0;
if ($edit) {
    $edit_kind = (isset($edit['kind']) && (string)$edit['kind'] === 'free') ? 'free' : 'paid';
    $edit_maxd = isset($edit['max_devices'])
        ? (int)$edit['max_devices']
        : ((int)$edit['bind_one'] === 1 ? 1 : 0);
    if ($edit_kind === 'free') {
        $edit_maxd = 0;
    }
}

page_header('卡密管理', 'cards');
foreach ($page_errors as $pe) {
    echo alert_box($pe, 'err');
}
?>

<div class="toolbar">
  <form method="get" action="<?php echo e(u('pages/cards.php')); ?>" class="filters">
    <input type="text" name="q" value="<?php echo e($q); ?>" placeholder="搜索卡密（支持部分匹配）" maxlength="64">
    <select name="status">
      <option value="all"<?php echo $status === 'all' ? ' selected' : ''; ?>>全部状态</option>
      <option value="active"<?php echo $status === 'active' ? ' selected' : ''; ?>>启用</option>
      <option value="disabled"<?php echo $status === 'disabled' ? ' selected' : ''; ?>>禁用</option>
    </select>
    <select name="exp">
      <option value="all"<?php echo $exp === 'all' ? ' selected' : ''; ?>>全部期限</option>
      <option value="expired"<?php echo $exp === 'expired' ? ' selected' : ''; ?>>已过期</option>
      <option value="soon"<?php echo $exp === 'soon' ? ' selected' : ''; ?>>7 天内到期</option>
      <option value="never"<?php echo $exp === 'never' ? ' selected' : ''; ?>>永不过期</option>
    </select>
    <select name="bind">
      <option value="all"<?php echo $bind === 'all' ? ' selected' : ''; ?>>全部绑定</option>
      <option value="bound"<?php echo $bind === 'bound' ? ' selected' : ''; ?>>已绑设备</option>
      <option value="unbound"<?php echo $bind === 'unbound' ? ' selected' : ''; ?>>未绑设备</option>
    </select>
    <select name="sort">
      <option value="new"<?php echo $sort === 'new' ? ' selected' : ''; ?>>最新优先</option>
      <option value="old"<?php echo $sort === 'old' ? ' selected' : ''; ?>>最早优先</option>
    </select>
    <select name="per">
      <?php foreach ($per_list as $pv) { ?>
        <option value="<?php echo $pv; ?>"<?php echo $per === $pv ? ' selected' : ''; ?>>每页 <?php echo $pv; ?></option>
      <?php } ?>
    </select>
    <input type="hidden" name="reveal" value="<?php echo $reveal ? '1' : '0'; ?>">
    <button type="submit" class="btn btn-sm">筛选</button>
    <a class="btn btn-sm" href="<?php echo e(u('pages/cards.php')); ?>">重置</a>
  </form>
  <div class="toolbar-right">
    <a class="btn btn-sm<?php echo $reveal ? ' btn-warn' : ''; ?>"
       href="<?php echo e(url_with(array('reveal' => $reveal ? '0' : '1', 'page' => 1))); ?>">
      <?php echo $reveal ? '🔒 隐藏明文' : '👁 显示明文'; ?>
    </a>
    <a class="btn btn-sm btn-primary" href="<?php echo e(u('pages/cards_new.php')); ?>">＋ 新建</a>
    <form method="post" action="<?php echo e(u('pages/cards_export.php')); ?>" class="inline">
      <?php echo csrf_field(); ?>
      <input type="hidden" name="format" value="csv">
      <?php foreach ($ret_params as $rk => $rv) { ?>
        <input type="hidden" name="<?php echo e($rk); ?>" value="<?php echo e($rv); ?>">
      <?php } ?>
      <button type="submit" class="btn btn-sm">⇧ 导出</button>
    </form>
  </div>
</div>

<p class="muted small">
  共 <?php echo number_format($total); ?> 条
  <?php if ($q !== '') { ?>· 搜索「<?php echo e($q); ?>」<?php } ?>
  <?php if ($batch === 'last') { ?>· <b>只显示最近一批生成的 <?php echo number_format(count($batch_ids)); ?> 条</b>
    <a href="<?php echo e(u('pages/cards.php')); ?>">清除</a><?php } ?>
  <?php if (!$reveal) { ?>· 卡密默认脱敏，点「显示明文」或每行复制按钮<?php } ?>
</p>

<?php if ($edit) { ?>
<section class="card card-edit">
  <div class="card-h">
    <h2>编辑卡密 <code><?php echo e(mask_card((string)$edit['card_key'])); ?></code></h2>
    <div class="card-h-act"><a class="btn btn-sm" href="<?php echo e(url_with(array('action' => null, 'id' => null))); ?>">取消</a></div>
  </div>
  <p class="muted small" style="margin:0 0 8px">
    公益卡：账号绑定在当前设备上，换设备就是新账号；不限设备数。
    付费卡：账号跟随这张卡；最多可绑 N 台设备（0 表示不限），可随时调整。
  </p>
  <form method="post" action="<?php echo e(u('pages/cards.php')); ?>" class="form-grid">
    <?php echo csrf_field(); ?>
    <input type="hidden" name="action" value="save">
    <input type="hidden" name="id" value="<?php echo (int)$edit['id']; ?>">
    <input type="hidden" name="ret" value="<?php echo e($ret_qs); ?>">

    <label class="fld"><span>卡密（不可修改）</span>
      <input type="text" value="<?php echo e((string)$edit['card_key']); ?>" readonly>
      <em>改卡密会让已发出去的卡失效，所以这里只读</em>
    </label>

    <label class="fld"><span>到期时间</span>
      <input type="datetime-local" name="expire_at" id="exp_at"
             value="<?php echo ((int)$edit['expire_at'] > 0) ? e(date('Y-m-d\TH:i', (int)$edit['expire_at'])) : ''; ?>">
      <em>留空 = 不过期；当前：<?php echo e(fmt_expire((int)$edit['expire_at'])); ?></em>
    </label>

    <label class="fld fld-check">
      <input type="checkbox" name="never" value="1" id="exp_never"<?php echo (int)$edit['expire_at'] === 0 ? ' checked' : ''; ?>>
      <span>永不过期</span>
    </label>

    <label class="fld"><span>卡类型（建好后不可修改）</span>
      <input type="text" value="<?php echo e(card_kind_label($edit_kind)); ?>" readonly>
      <em>改类型会让该卡下所有设备的账号永久失联，因此只读；要换类型请新建卡。</em>
    </label>
    <input type="hidden" name="kind" value="<?php echo e($edit_kind); ?>">

    <label class="fld"><span>最大设备数</span>
      <input type="number" name="max_devices" value="<?php echo (int)$edit_maxd; ?>" min="0" max="9999"<?php echo $edit_kind === 'free' ? ' disabled' : ''; ?>>
      <em>0 = 不限；1 = 最多一台；N = 最多 N 台。公益卡固定不限；付费卡可随时改，保存即生效。</em>
    </label>

    <label class="fld"><span>状态</span>
      <select name="status">
        <option value="active"<?php echo $edit['status'] === 'active' ? ' selected' : ''; ?>>启用</option>
        <option value="disabled"<?php echo $edit['status'] === 'disabled' ? ' selected' : ''; ?>>禁用</option>
      </select>
    </label>

    <label class="fld"><span>备注</span>
      <input type="text" name="note" value="<?php echo e((string)$edit['note']); ?>" maxlength="255">
    </label>

    <div class="fld fld-wide fld-actions">
      <button type="submit" class="btn btn-primary">保存修改</button>
      <?php if (!empty($devmap[(int)$edit['id']])) { ?>
        <span class="muted small">已绑定 <?php echo count($devmap[(int)$edit['id']]); ?> 台：
          <?php foreach ($devmap[(int)$edit['id']] as $d) { ?>
            <code class="small"><?php echo e($d['device_id']); ?></code>
          <?php } ?>
        </span>
      <?php } ?>
    </div>
  </form>
</section>
<?php } ?>

<div class="bulkbar">
  <form method="post" action="<?php echo e(u('pages/cards.php')); ?>" id="bulkform"
        onsubmit="return CA.confirmBulk(this);">
    <?php echo csrf_field(); ?>
    <input type="hidden" name="action" value="bulk">
    <input type="hidden" name="ret" value="<?php echo e($ret_qs); ?>">
    <label class="chk"><input type="checkbox" id="ca-check-all"> 全选本页</label>
    <select name="op">
      <option value="enable">启用</option>
      <option value="disable">禁用</option>
      <option value="delete">删除</option>
      <option value="extend">延期 N 天</option>
      <option value="never">设为永不过期</option>
      <option value="unbind">解绑设备</option>
    </select>
    <input type="number" name="days" value="30" min="1" max="36500" class="days" title="延期天数">
    <button type="submit" class="btn btn-sm btn-primary">对选中项执行</button>
    <span class="muted small" id="ca-sel-count">已选 0 条</span>
  </form>
</div>

<!-- 行操作统一用一个表单（避免表格里嵌套 form） -->
<form method="post" action="<?php echo e(u('pages/cards.php')); ?>" id="rowact">
  <?php echo csrf_field(); ?>
  <input type="hidden" name="action" value="row">
  <input type="hidden" name="id" id="ca-row-id" value="">
  <input type="hidden" name="op" id="ca-row-op" value="">
  <input type="hidden" name="ret" value="<?php echo e($ret_qs); ?>">
</form>

<div class="table-wrap">
<table class="tbl tbl-cards">
  <thead>
    <tr>
      <th class="w-chk"></th>
      <th>卡密</th>
      <th>状态</th>
      <th>类型</th>
      <th>到期</th>
      <th>设备</th>
      <th>玩家</th>
      <th>创建</th>
      <th>最后登录</th>
      <th class="w-act">操作</th>
    </tr>
  </thead>
  <tbody>
  <?php if (!$rows) { ?>
    <tr><td colspan="10" class="empty">没有匹配的卡密</td></tr>
  <?php } ?>
  <?php foreach ($rows as $r) {
      $cid   = (int)$r['id'];
      $key   = (string)$r['card_key'];
      $devs  = isset($devmap[$cid]) ? $devmap[$cid] : array();
      $expat = (int)$r['expire_at'];
      $disabled = $r['status'] === 'disabled';
      ?>
    <tr class="<?php echo $disabled ? 'row-off' : ''; ?>">
      <td class="w-chk"><input type="checkbox" name="ids[]" value="<?php echo $cid; ?>" form="bulkform" class="ca-pick"></td>
      <td class="td-key">
        <?php if ($reveal) { ?>
          <code class="key"><?php echo e($key); ?></code>
        <?php } else { ?>
          <code class="key masked" data-card="<?php echo e(mask_card($key)); ?>"><?php echo e(mask_card($key)); ?></code>
        <?php } ?>
        <?php if (!card_key_is_client_compatible($key)) { ?>
          <span class="tag tag-err" title="客户端正则 ^1\d{10}$：只认 1 开头的 11 位数字，这张卡在客户端输不进去">客户端不可用</span>
        <?php } ?>
        <button type="button" class="btn-copy" data-fetch="<?php echo e(u('pages/cards.php')); ?>"
                data-id="<?php echo $cid; ?>" data-csrf="<?php echo e(csrf_token()); ?>"
                <?php echo $reveal ? 'data-copy="' . e($key) . '"' : ''; ?> title="复制卡密">复制</button>
        <?php if ((string)$r['note'] !== '') { ?>
          <div class="note muted small"><?php echo e(str_limit((string)$r['note'], 40)); ?></div>
        <?php } ?>
      </td>
      <td>
        <?php if ($disabled) { ?>
          <span class="tag tag-err">已禁用</span>
        <?php } elseif (is_expired($expat)) { ?>
          <span class="tag tag-warn">已过期</span>
        <?php } else { ?>
          <span class="tag tag-ok">启用</span>
        <?php } ?>
      </td>
      <td class="nowrap">
        <?php
        $row_kind = (isset($r['kind']) && (string)$r['kind'] === 'free') ? 'free' : 'paid';
        $row_maxd = isset($r['max_devices']) ? (int)$r['max_devices'] : ((int)$r['bind_one'] === 1 ? 1 : 0);
        ?>
        <span class="tag <?php echo $row_kind === 'free' ? 'tag-warn' : 'tag-ok'; ?>"><?php echo e(card_kind_label($row_kind)); ?></span>
        <div class="muted small"><?php echo e(card_devices_text($row_kind, $row_maxd)); ?></div>
      </td>
      <td class="nowrap">
        <?php if ($expat === 0) { ?>
          <span class="muted">永不</span>
        <?php } else { ?>
          <span class="<?php echo is_expired($expat) ? 'bad' : ''; ?>"><?php echo e(date('Y-m-d H:i', $expat)); ?></span>
          <div class="muted small"><?php echo e(human_left($expat)); ?></div>
        <?php } ?>
      </td>
      <td>
        <?php if (!$devs) { ?>
          <span class="muted">—</span>
        <?php } else { ?>
          <span class="tag tag-info"><?php echo count($devs); ?> 台</span>
          <div class="devs small">
            <?php $n = 0; foreach ($devs as $d) { $n++; if ($n > 3) { echo '<span class="muted">…</span>'; break; } ?>
              <code class="small" title="<?php echo e($d['device_id']); ?>"><?php echo e(str_limit($d['device_id'], 16)); ?></code>
            <?php } ?>
          </div>
        <?php } ?>
      </td>
      <td class="nowrap">
        <?php $bnd = isset($bindmap[$cid]) ? $bindmap[$cid] : null; ?>
        <?php if ($bnd && (int)$bnd['server_id'] > 0) { ?>
          <a class="small" href="<?php echo e(u('pages/player_detail.php?sid=' . (int)$bnd['server_id'])); ?>">#<?php echo (int)$bnd['server_id']; ?></a>
          <?php if ((string)$bnd['source'] !== 'manual') { ?><div class="muted small"><?php echo e((string)$bnd['source']); ?></div><?php } ?>
        <?php } elseif ($bnd) { ?>
          <span class="muted small">publisher <?php echo e((string)$bnd['publisher_account_id']); ?></span>
        <?php } else { ?>
          <span class="muted small">—</span>
        <?php } ?>
      </td>
      <td class="nowrap muted small"><?php echo e(fmt_dt($r['created_at'])); ?><?php
        if ((string)$r['created_by'] !== '') { ?><div><?php echo e(str_limit((string)$r['created_by'], 14)); ?></div><?php } ?></td>
      <td class="nowrap muted small">
        <?php if ((string)$r['last_login_at'] === '' || $r['last_login_at'] === null) { ?>
          —
        <?php } else { ?>
          <?php echo e(fmt_dt($r['last_login_at'])); ?>
          <?php if ((int)$r['login_count'] > 0) { ?><div>共 <?php echo (int)$r['login_count']; ?> 次</div><?php } ?>
        <?php } ?>
      </td>
      <td class="w-act nowrap">
        <a class="btn btn-xs" href="<?php echo e(url_with(array('action' => 'edit', 'id' => $cid))); ?>">编辑</a>
        <a class="btn btn-xs" href="<?php echo e(u('pages/logs.php?card_id=' . $cid)); ?>">日志</a>
        <button type="button" class="btn btn-xs" data-act="unbind" data-id="<?php echo $cid; ?>">解绑</button>
        <?php if ($disabled) { ?>
          <button type="button" class="btn btn-xs" data-act="enable" data-id="<?php echo $cid; ?>">启用</button>
        <?php } else { ?>
          <button type="button" class="btn btn-xs" data-act="disable" data-id="<?php echo $cid; ?>">禁用</button>
        <?php } ?>
        <button type="button" class="btn btn-xs btn-danger" data-act="delete" data-id="<?php echo $cid; ?>"
                data-confirm="确认删除该卡密？删除后客户端立刻失效（60 秒内）。">删除</button>
      </td>
    </tr>
  <?php } ?>
  </tbody>
</table>
</div>

<?php echo pagination($page, $per, $total, array(), 'pages/cards.php'); ?>

<p class="muted small">
  提示：删除/禁用/延期等操作只改数据库，cron 同步后（≤60 秒）才影响客户端；
  改了之后可到「仪表盘 → 立即同步」马上推一次。
</p>

<script>
(function () {
  var m = document.querySelector('input[name="max_devices"]');
  var h = document.querySelector('input[name="kind"]');
  if (m && h && h.value === 'free') { m.value = '0'; m.disabled = true; }
})();
</script>

<?php page_footer(); ?>
