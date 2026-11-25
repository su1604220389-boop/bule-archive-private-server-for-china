<?php
/**
 * pages/currency.php —— 批量货币调整
 *
 * 三种模式：
 *   set   设为绝对值（服务端 currency/set 语义）
 *   add   在当前值上增加（读现值 → 写 现值+N）
 *   sub   在当前值上减少（读现值 → 写 max(0, 现值-N)）
 *
 * 注意青辉石：合计 Gem(4) 是派生的，写它等价于"免费石=该值、付费石=0"。
 * 想要"只加免费石"请选 GemBonus(3)。
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';
require_once __DIR__ . '/../inc/ba.php';
require_once __DIR__ . '/../inc/players.php';

require_login();

$cur = ba_currency_maps();
$preselect = array();
if (isset($_GET['sid'])) {
    foreach ((array)$_GET['sid'] as $v) {
        foreach (explode(',', (string)$v) as $p) {
            $p = (int)trim($p);
            if ($p > 0) {
                $preselect[$p] = $p;
            }
        }
    }
}

$result = null;

if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    require_post_csrf();
    action_token_check('currency');

    $scope  = post_q('scope', 'selected');
    $mode   = post_q('mode', 'set');
    $type   = post_int('currency_type', 0);
    $amount = post_int('amount', 0, 0);

    $ids = array();
    foreach ((array)(isset($_POST['sid']) ? $_POST['sid'] : array()) as $v) {
        $v = (int)$v;
        if ($v > 0) {
            $ids[$v] = $v;
        }
    }
    $ids = array_values($ids);

    if ($scope === 'all') {
        $roster = player_roster(array());
        $ids = array();
        if ($roster['ok']) {
            foreach ($roster['rows'] as $rr) {
                $ids[] = (int)$rr['server_id'];
            }
        }
    }

    if ($type <= 0) {
        flash_set('先选货币类型', 'err');
        redirect_self();
    }
    if (!$ids) {
        flash_set('没有选中任何玩家', 'err');
        redirect_self();
    }

    $batch = substr(bin2hex(random_bytes(6)), 0, 12);
    $rows  = array();
    $okN   = 0;
    $failN = 0;
    $cname = isset($cur['id2name'][$type]) ? $cur['id2name'][$type] : ('#' . $type);

    foreach ($ids as $sid) {
        $before = null;
        $dict = ba_account_currencies($sid);
        if (!$dict['ok'] || !is_array($dict['data'])) {
            $rows[] = array('sid' => $sid, 'ok' => false, 'msg' => '读不到现值：' . $dict['error'], 'before' => null, 'after' => null);
            $failN++;
            continue;
        }
        $before = isset($dict['data'][$cname]) ? (int)$dict['data'][$cname] : 0;
        if ($mode === 'add') {
            $target = $before + $amount;
        } elseif ($mode === 'sub') {
            $target = max(0, $before - $amount);
        } else {
            $target = $amount;
        }

        $r = ba_currency_set($sid, $type, $target);
        $rows[] = array(
            'sid'    => $sid,
            'ok'     => (bool)$r['ok'],
            'msg'    => $r['ok'] ? '已写入' : $r['error'],
            'before' => $before,
            'after'  => $r['ok'] ? $target : null,
        );
        if ($r['ok']) {
            $okN++;
        } else {
            $failN++;
        }
    }

    panel_op_log('currency.batch', $ids, array(
        'batch' => $batch, 'currency' => $cname, 'type' => $type, 'mode' => $mode, 'amount' => $amount,
    ), $okN, $failN, $batch);

    /* F3：audit_logs 补一条，带每人「旧值→新值」（失败记 fail） */
    $diffs = array();
    foreach ($rows as $rr) {
        $diffs[] = $rr['sid'] . ':' . ($rr['before'] === null ? '?' : $rr['before'])
                 . '→' . ($rr['after'] === null ? 'fail' : $rr['after']);
    }
    audit_log('currency.batch',
        '货币 ' . $cname . '(#' . $type . ') 模式=' . $mode . ' 数量=' . $amount . ' 共' . count($ids) . '人',
        'batch=' . $batch . ' ' . implode(' ', array_slice($diffs, 0, 80)));

    $result = array('batch' => $batch, 'rows' => $rows, 'ok' => $okN, 'fail' => $failN,
                    'currency' => $cname, 'mode' => $mode, 'amount' => $amount);
}

$roster = player_roster(array());
$allPlayers = $roster['ok'] ? $roster['rows'] : array();

page_header('货币调整', 'currency');
if (!$roster['ok']) {
    echo '<div class="srv-down">读取不到游戏服务端：<b>' . e($roster['error']) . '</b></div>';
}
?>

<?php if ($result) { ?>
<section class="card card-result">
  <div class="card-h"><h2>调整结果</h2>
    <div class="card-h-act">
      <span class="tag <?php echo $result['fail'] ? 'tag-warn' : 'tag-ok'; ?>">
        成功 <?php echo (int)$result['ok']; ?> / 失败 <?php echo (int)$result['fail']; ?></span>
      <code class="small">batch <?php echo e($result['batch']); ?></code>
    </div>
  </div>
  <div class="table-wrap">
  <table class="tbl">
    <thead><tr><th>ServerId</th><th><?php echo e($result['currency']); ?> 变更</th><th>结果</th></tr></thead>
    <tbody>
    <?php foreach ($result['rows'] as $rr) { ?>
      <tr>
        <td><a href="<?php echo e(u('pages/player_detail.php?sid=' . $rr['sid'])); ?>">#<?php echo (int)$rr['sid']; ?></a></td>
        <td class="nowrap">
          <?php if ($rr['before'] !== null) { echo number_format((int)$rr['before']) . ' → '; } ?>
          <?php echo $rr['after'] !== null ? '<b>' . number_format((int)$rr['after']) . '</b>' : '—'; ?>
        </td>
        <td><?php echo $rr['ok'] ? '<span class="tag tag-ok">' . e($rr['msg']) . '</span>'
                                  : '<span class="tag tag-err">' . e($rr['msg']) . '</span>'; ?></td>
      </tr>
    <?php } ?>
    </tbody>
  </table>
  </div>
</section>
<?php } ?>

<section class="card">
  <div class="card-h"><h2>批量调整货币</h2></div>
  <form method="post" action="<?php echo e(u('pages/currency.php')); ?>">
    <?php echo csrf_field(); ?>
    <?php echo action_token_field('currency'); ?>

    <div class="field">
      <label><b>对象</b></label>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:6px">
        <label class="small"><input type="radio" name="scope" value="selected" checked> 指定玩家</label>
        <label class="small"><input type="radio" name="scope" value="all"> 全服（<?php echo count($allPlayers); ?> 人）</label>
        <button type="button" class="btn btn-xs" id="sel-all">全选</button>
        <button type="button" class="btn btn-xs" id="sel-none">清空</button>
        <span class="muted small" id="sel-count"></span>
      </div>
      <div style="max-height:180px;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:8px">
        <?php foreach ($allPlayers as $p) { $psid = (int)$p['server_id']; ?>
          <label class="small" style="display:block;padding:2px 0">
            <input type="checkbox" name="sid[]" value="<?php echo $psid; ?>" class="msid"
                   <?php echo isset($preselect[$psid]) ? ' checked' : ''; ?>>
            <?php echo e($p['nickname'] !== '' ? $p['nickname'] : '（无昵称）'); ?>
            <span class="muted">#<?php echo $psid; ?> · Lv<?php echo (int)$p['level']; ?></span>
          </label>
        <?php } ?>
        <?php if (!$allPlayers) { ?><span class="muted small">还没有玩家</span><?php } ?>
      </div>
    </div>

    <div class="field-row">
      <div class="field"><label><b>货币</b></label>
        <select name="currency_type">
          <?php foreach ($cur['id2name'] as $cid => $cname) { ?>
            <option value="<?php echo (int)$cid; ?>"<?php echo (int)$cid === 3 ? ' selected' : ''; ?>>
              <?php echo e(ba_currency_label($cid, $cname)); ?></option>
          <?php } ?>
        </select>
      </div>
      <div class="field"><label><b>模式</b></label>
        <select name="mode">
          <option value="set">设为（绝对值）</option>
          <option value="add">增加（+N）</option>
          <option value="sub">减少（-N）</option>
        </select>
      </div>
      <div class="field"><label><b>数量</b></label>
        <input type="number" name="amount" value="1000" step="1">
      </div>
    </div>

    <?php echo alert_box('青辉石三条路：GemBonus(3)=免费石、GemPaid(2)=付费石、Gem(4)=合计。'
        . '写合计会把免费石设成该值、付费石清零；想叠加请用 GemBonus。', 'info'); ?>

    <div class="actions">
      <button type="submit" class="btn btn-primary">执行</button>
      <a class="btn" href="<?php echo e(u('pages/players.php')); ?>">返回玩家列表</a>
    </div>
  </form>
</section>

<script>
(function () {
  var picks = Array.prototype.slice.call(document.querySelectorAll('.msid'));
  var counter = document.getElementById('sel-count');
  function sync() {
    var n = picks.filter(function (c) { return c.checked; }).length;
    if (counter) { counter.textContent = '已选 ' + n + ' 人'; }
  }
  picks.forEach(function (c) { c.addEventListener('change', sync); });
  sync();
  var sa = document.getElementById('sel-all');
  if (sa) { sa.addEventListener('click', function () { picks.forEach(function (c) { c.checked = true; }); sync(); }); }
  var sn = document.getElementById('sel-none');
  if (sn) { sn.addEventListener('click', function () { picks.forEach(function (c) { c.checked = false; }); sync(); }); }
})();
</script>

<?php page_footer(); ?>
