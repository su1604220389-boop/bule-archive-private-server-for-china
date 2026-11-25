<?php
/**
 * pages/mail.php —— 发奖 / 发邮件 / 补偿
 *
 * 支持：单人 / 多选批量 / 全服。
 * 附件可以混搭（货币 + 道具 + 角色 + 记忆大厅 …），每行一个附件。
 * 真正入账发生在玩家在游戏里"领取邮件"那一刻，走 Shittim 自己的 ParcelResolver。
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';
require_once __DIR__ . '/../inc/ba.php';
require_once __DIR__ . '/../inc/players.php';

require_login();

$cur   = ba_currency_maps();
$types = ba_parcel_presets();

/* 解析 ?sid=2,3 或 ?sid[]=2&sid[]=3 */
$preselect = array();
if (isset($_GET['sid'])) {
    $raw = $_GET['sid'];
    foreach ((array)$raw as $v) {
        foreach (explode(',', (string)$v) as $p) {
            $p = (int)trim($p);
            if ($p > 0) {
                $preselect[$p] = $p;
            }
        }
    }
}

$result  = null;

/* ------------------------------------------------------------------ POST --- */
if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    require_post_csrf();
    action_token_check('mail');

    $scope   = post_q('scope', 'selected');       // selected | all
    $ids     = array();
    foreach ((array)(isset($_POST['sid']) ? $_POST['sid'] : array()) as $v) {
        $v = (int)$v;
        if ($v > 0) {
            $ids[$v] = $v;
        }
    }
    $ids = array_values($ids);

    $sender  = trim((string)post_q('sender', 'Schale'));
    $comment = (string)post_q('comment', '');
    $expire  = trim((string)post_q('expire', ''));

    if ($sender === '') {
        $sender = 'Schale';
    }

    /* 收集附件 */
    $parcels = array();
    $ptypes  = (array)(isset($_POST['p_type']) ? $_POST['p_type'] : array());
    $pidSel  = (array)(isset($_POST['p_id']) ? $_POST['p_id'] : array());
    $pidNum  = (array)(isset($_POST['p_id_num']) ? $_POST['p_id_num'] : array());
    $pamts   = (array)(isset($_POST['p_amount']) ? $_POST['p_amount'] : array());
    foreach ($ptypes as $i => $t) {
        $t = trim((string)$t);
        if ($t === '') {
            continue;
        }
        $amt = isset($pamts[$i]) ? (int)$pamts[$i] : 0;
        if ($amt <= 0) {
            continue;
        }
        /* 货币用下拉框的 id；其它类型用数字输入框的 id（两个控件每行都提交，按 type 取其一） */
        if ($t === 'Currency') {
            $id = isset($pidSel[$i]) ? (int)$pidSel[$i] : 0;
        } else {
            $id = isset($pidNum[$i]) ? (int)$pidNum[$i] : 0;
        }
        $parcels[] = array('type' => $t, 'id' => $id, 'amount' => $amt);
    }

    if ($scope === 'all') {
        $roster = player_roster(array());
        $ids = array();
        if ($roster['ok']) {
            foreach ($roster['rows'] as $rr) {
                $ids[] = (int)$rr['server_id'];
            }
        }
    }

    $errs = array();
    if (!$ids) {
        $errs[] = '没有选中任何玩家';
    }
    if (!$parcels) {
        $errs[] = '至少填一个数量大于 0 的附件';
    }
    if ($comment === '') {
        $errs[] = '邮件内容不能为空';
    }
    /* 角色排除名单（客户端解析不了的角色，服务端已剔除，面板再拦一道） */
    $denyErr = ba_validate_parcels($parcels);
    if ($denyErr !== '') {
        $errs[] = $denyErr;
    }

    if ($errs) {
        flash_set(implode('；', $errs), 'err');
        redirect_self();
    }

    $batch  = substr(bin2hex(random_bytes(6)), 0, 12);
    $rows   = array();
    $okN    = 0;
    $failN  = 0;
    foreach ($ids as $sid) {
        $r = ba_mail_send($sid, $sender, $comment, $parcels, $expire);
        $rows[] = array(
            'sid'  => $sid,
            'ok'   => (bool)$r['ok'],
            'msg'  => $r['ok'] ? '已投递' : $r['error'],
            'ms'   => (int)$r['ms'],
        );
        if ($r['ok']) {
            $okN++;
        } else {
            $failN++;
        }
    }

    panel_op_log('mail.send', $ids, array(
        'batch'   => $batch,
        'sender'  => $sender,
        'comment' => $comment,
        'expire'  => $expire,
        'parcels' => $parcels,
    ), $okN, $failN, $batch);

    /* F3：audit_logs 补一条（发奖是可追溯性要求最高的操作），含完整附件与收件人数 */
    audit_log('mail.send',
        '邮件批次 ' . $batch . ' → ' . count($ids) . ' 人（成功 ' . $okN . ' / 失败 ' . $failN . '）',
        'sender=' . $sender . ' expire=' . ($expire === '' ? '默认7天' : $expire)
        . ' comment=' . str_limit($comment, 200)
        . ' parcels=' . json_encode($parcels, JSON_UNESCAPED_UNICODE)
        . ' ids=' . implode(',', array_slice($ids, 0, 80)));

    $result = array('batch' => $batch, 'rows' => $rows, 'ok' => $okN, 'fail' => $failN,
                    'parcels' => $parcels, 'comment' => $comment);
}

/* ------------------------------------------------------------------ 数据 --- */
$roster = player_roster(array());
$allPlayers = $roster['ok'] ? $roster['rows'] : array();
$itemsSample = array();
$r0 = ba_static_items('', 300);
if ($r0['ok'] && is_array($r0['data'])) {
    $itemsSample = $r0['data'];
}
$charsSample = array();
$r1 = ba_static_characters('', 500);
if ($r1['ok'] && is_array($r1['data'])) {
    $charsSample = $r1['data'];
}

page_header('发奖 / 邮件', 'mail');
if (!$roster['ok']) {
    echo '<div class="srv-down">读取不到游戏服务端：<b>' . e($roster['error']) . '</b></div>';
}
?>

<?php if ($result) { ?>
<section class="card card-result">
  <div class="card-h"><h2>发送结果</h2>
    <div class="card-h-act"><span class="tag <?php echo $result['fail'] ? 'tag-warn' : 'tag-ok'; ?>">
      成功 <?php echo (int)$result['ok']; ?> / 失败 <?php echo (int)$result['fail']; ?></span>
      <code class="small">batch <?php echo e($result['batch']); ?></code>
    </div>
  </div>
  <div class="table-wrap">
  <table class="tbl">
    <thead><tr><th>ServerId</th><th>结果</th><th>耗时</th></tr></thead>
    <tbody>
    <?php foreach ($result['rows'] as $rr) { ?>
      <tr>
        <td><a href="<?php echo e(u('pages/player_detail.php?sid=' . $rr['sid'])); ?>">#<?php echo (int)$rr['sid']; ?></a></td>
        <td><?php echo $rr['ok'] ? '<span class="tag tag-ok">' . e($rr['msg']) . '</span>'
                                  : '<span class="tag tag-err">' . e($rr['msg']) . '</span>'; ?></td>
        <td class="muted small"><?php echo (int)$rr['ms']; ?> ms</td>
      </tr>
    <?php } ?>
    </tbody>
  </table>
  </div>
  <p class="muted small">邮件已进邮箱，<b>玩家在游戏里点领取才真正到账</b>（青辉石走 ParcelResolver 的 GEMGRANT 分支，落到 GemBonus）。</p>
</section>
<?php } ?>

<section class="card">
  <div class="card-h"><h2>发奖</h2>
    <div class="card-h-act">
      <button type="button" class="btn btn-sm" data-quick="gem">💎 青辉石</button>
      <button type="button" class="btn btn-sm" data-quick="gold">💰 金币</button>
      <button type="button" class="btn btn-sm" data-quick="ap">⚡ 体力</button>
      <button type="button" class="btn btn-sm" data-quick="combo">🎁 三件套</button>
    </div>
  </div>

  <form method="post" action="<?php echo e(u('pages/mail.php')); ?>" id="mail-form">
    <?php echo csrf_field(); ?>
    <?php echo action_token_field('mail'); ?>

    <div class="field">
      <label><b>收件人</b></label>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:6px">
        <label class="small"><input type="radio" name="scope" value="selected" checked> 指定玩家</label>
        <label class="small"><input type="radio" name="scope" value="all"> 全服（<?php echo count($allPlayers); ?> 人）</label>
        <button type="button" class="btn btn-xs" id="sel-all">全选</button>
        <button type="button" class="btn btn-xs" id="sel-none">清空</button>
        <span class="muted small" id="sel-count"></span>
      </div>
      <div style="max-height:180px;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:8px">
        <?php if (!$allPlayers) { ?>
          <span class="muted small">还没有玩家（服务端无账号或未连通）</span>
        <?php } ?>
        <?php foreach ($allPlayers as $p) { $psid = (int)$p['server_id']; ?>
          <label class="small" style="display:block;padding:2px 0">
            <input type="checkbox" name="sid[]" value="<?php echo $psid; ?>" class="msid"
                   <?php echo isset($preselect[$psid]) ? ' checked' : ''; ?>>
            <?php echo e($p['nickname'] !== '' ? $p['nickname'] : '（无昵称）'); ?>
            <span class="muted">#<?php echo $psid; ?> · Lv<?php echo (int)$p['level']; ?></span>
            <?php if (player_is_banned($p['state'])) { ?><span class="tag tag-err">已封禁</span><?php } ?>
          </label>
        <?php } ?>
      </div>
    </div>

    <div class="field">
      <label><b>发送者</b></label>
      <input type="text" name="sender" value="Schale" maxlength="64" style="max-width:240px">
      <span class="muted small">游戏里显示的发件人</span>
    </div>

    <div class="field">
      <label><b>邮件内容</b></label>
      <textarea name="comment" rows="3" maxlength="500" placeholder="例如：本次维护补偿，请查收。"></textarea>
    </div>

    <div class="field">
      <label><b>有效期</b></label>
      <input type="datetime-local" name="expire" style="max-width:240px">
      <span class="muted small">留空 = 默认 7 天</span>
    </div>

    <div class="field">
      <label><b>附件</b>（可以混搭，留空的行会被忽略）</label>
      <div id="parcel-rows">
        <?php
        $rows0 = array(
            array('Currency', $cur['name2id']['GemBonus'] ?? 3, 1000),
            array('', 0, 0),
            array('', 0, 0),
        );
        foreach ($rows0 as $n => $def) {
            list($dt, $di, $da) = $def;
            ?>
          <div class="parcel-row">
            <select name="p_type[]" class="p-type" onchange="window.__ptype(this)">
              <option value="">（不使用）</option>
              <?php foreach ($types as $tv => $tl) { ?>
                <option value="<?php echo e($tv); ?>"<?php echo $dt === $tv ? ' selected' : ''; ?>><?php echo e($tl); ?></option>
              <?php } ?>
            </select>

            <span class="p-id-wrap">
              <select name="p_id[]" class="p-id-cur"<?php echo $dt === 'Currency' ? '' : ' style="display:none"'; ?>>
                <?php foreach ($cur['id2name'] as $cid => $cname) { ?>
                  <option value="<?php echo (int)$cid; ?>"<?php echo (int)$di === (int)$cid ? ' selected' : ''; ?>>
                    <?php echo e(ba_currency_label($cid, $cname)); ?></option>
                <?php } ?>
              </select>
              <input type="number" name="p_id_num[]" class="p-id-num" min="0" step="1"
                     value="<?php echo $dt !== '' && $dt !== 'Currency' ? (int)$di : ''; ?>"
                     placeholder="ID（道具/角色/装备的 Excel Id）"
                     list="dl-any"<?php echo $dt === 'Currency' ? ' style="display:none"' : ''; ?>>
            </span>

            <input type="number" name="p_amount[]" class="p-amt" min="0" step="1"
                   value="<?php echo $da > 0 ? (int)$da : ''; ?>" placeholder="数量">

            <button type="button" class="btn btn-xs" onclick="window.__pdel(this)" title="清空这一行">✕</button>
          </div>
        <?php } ?>
      </div>

      <datalist id="dl-any">
        <?php foreach ($charsSample as $c) { if (!isset($c['id'])) { continue; } ?>
          <option value="<?php echo (int)$c['id']; ?>">角色 <?php echo e(isset($c['name']) ? $c['name'] : ''); ?></option>
        <?php } ?>
        <?php foreach ($itemsSample as $it) { if (!isset($it['id'])) { continue; } ?>
          <option value="<?php echo (int)$it['id']; ?>">道具 <?php echo e(isset($it['name']) ? $it['name'] : ''); ?></option>
        <?php } ?>
      </datalist>

      <p class="muted small" style="margin-top:6px">
        <b>货币</b>：Id 用货币枚举（青辉石免费=3 GemBonus、付费=2 GemPaid、合计=4 Gem、金币=1、体力=5）。<br>
        <b>角色/道具/装备</b>：Id 填 Excel 的 Id，可以边打字边从下拉提示里选。<br>
        具体 Id 可以到「道具 / 角色」页的静态数据表里查。<br>
        <b class="bad">角色注意</b>：当前客户端有 <?php echo count(ba_denied_character_ids()); ?> 个角色无法解析，
        服务端已剔除，面板也会拒绝：<span class="muted"><?php echo e(implode('、', ba_denied_character_ids())); ?></span>
      </p>
    </div>

    <div class="actions">
      <button type="submit" class="btn btn-primary">发送</button>
      <a class="btn" href="<?php echo e(u('pages/players.php')); ?>">返回玩家列表</a>
    </div>
  </form>
</section>

<?php
$recent = panel_op_recent(10);
if ($recent) { ?>
<section class="card">
  <div class="card-h"><h2>最近 10 批发奖</h2>
    <div class="card-h-act"><a class="btn btn-sm" href="<?php echo e(u('pages/audit.php')); ?>">审计日志</a></div>
  </div>
  <div class="table-wrap">
  <table class="tbl">
    <thead><tr><th>时间</th><th>批次</th><th>对象</th><th>内容</th><th>结果</th><th>操作人</th></tr></thead>
    <tbody>
    <?php foreach ($recent as $op) {
        $pl = json_decode((string)$op['payload'], true);
        $desc = '';
        if (is_array($pl) && isset($pl['parcels'])) {
            $bits = array();
            foreach ($pl['parcels'] as $pc) {
                $nm = $pc['type'];
                if ($pc['type'] === 'Currency') {
                    $nm = isset($cur['id2name'][(int)$pc['id']]) ? $cur['id2name'][(int)$pc['id']] : ('Currency#' . $pc['id']);
                }
                $bits[] = $nm . '×' . number_format((int)$pc['amount']);
            }
            $desc = implode(' + ', $bits);
            if (isset($pl['comment'])) {
                $desc .= '　「' . str_limit((string)$pl['comment'], 18) . '」';
            }
        }
        $tg = (string)$op['targets'];
        ?>
      <tr>
        <td class="nowrap"><?php echo e(fmt_ts((int)$op['ts'])); ?></td>
        <td><code class="small"><?php echo e((string)$op['batch_id']); ?></code></td>
        <td class="small"><?php echo count(array_filter(explode(',', $tg))) ?: 0; ?> 人</td>
        <td class="small"><?php echo e($desc); ?></td>
        <td class="nowrap">
          <span class="tag tag-ok"><?php echo (int)$op['ok_count']; ?></span>
          <?php if ((int)$op['fail_count'] > 0) { ?><span class="tag tag-err"><?php echo (int)$op['fail_count']; ?></span><?php } ?>
        </td>
        <td class="small muted"><?php echo e((string)$op['admin_name']); ?></td>
      </tr>
    <?php } ?>
    </tbody>
  </table>
  </div>
</section>
<?php } ?>

<script>
window.__ptype = function (sel) {
  var row = sel.closest('.parcel-row');
  var isCur = sel.value === 'Currency';
  row.querySelector('.p-id-cur').style.display = isCur ? '' : 'none';
  row.querySelector('.p-id-num').style.display = (sel.value === '' || isCur) ? 'none' : '';
};
window.__pdel = function (btn) {
  var row = btn.closest('.parcel-row');
  row.querySelector('.p-type').value = '';
  row.querySelector('.p-amt').value = '';
  window.__ptype(row.querySelector('.p-type'));
};

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

  /* 快捷模板：直接改前几行附件 */
  var CURR = <?php echo json_encode($cur['name2id'], JSON_UNESCAPED_UNICODE); ?>;
  document.querySelectorAll('[data-quick]').forEach(function (b) {
    b.addEventListener('click', function () {
      var rows = Array.prototype.slice.call(document.querySelectorAll('.parcel-row'));
      function setRow(row, curId, amt) {
        var t = row.querySelector('.p-type');
        t.value = 'Currency';
        window.__ptype(t);
        row.querySelector('.p-id-cur').value = String(curId);
        row.querySelector('.p-amt').value = String(amt);
      }
      var GEMB = CURR['GemBonus'] || 3;
      var GOLD = CURR['Gold'] || 1;
      var AP   = CURR['ActionPoint'] || 5;
      var q = b.getAttribute('data-quick');
      if (q === 'gem')   { setRow(rows[0], GEMB, 1200); }
      if (q === 'gold')  { setRow(rows[0], GOLD, 1000000); }
      if (q === 'ap')    { setRow(rows[0], AP, 500); }
      if (q === 'combo') {
        setRow(rows[0], GEMB, 1200);
        setRow(rows[1], GOLD, 1000000);
        setRow(rows[2], AP, 500);
      }
    });
  });
})();
</script>

<?php page_footer(); ?>
